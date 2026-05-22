"""Agent 主循环 (ReAct)"""

from __future__ import annotations

import json
from typing import Any

import httpx

from bot001.config import AgentConfig
from bot001.executor import Executor
from bot001.message import Message, ToolCall
from bot001.memory.short_term import ShortTermMemory
from bot001.memory.long_term import LongTermMemory
from bot001.session import SessionManager
from bot001.tools.registry import ToolRegistry


class LLMClient:
    """LLM 调用客户端"""

    def __init__(self, config):
        self.api_base = config.api_base
        self.api_key = config.api_key
        self.model = config.model
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict[str, Any]:
        """调用 LLM"""
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{self.api_base.rstrip('/')}/chat/completions",
                json=body,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()


class Agent:
    """Agent 主循环 (ReAct)"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm = LLMClient(config.llm)
        self.registry = ToolRegistry()
        self.session_manager = SessionManager(config.db_path)
        self.long_term = LongTermMemory(config.db_path)
        self.executor = Executor(self.registry)

        # 注册内置工具
        from bot001.tools.builtin import register_builtin_tools
        register_builtin_tools(self.registry)

        self._load_skills()

    def _load_skills(self) -> None:
        """加载 skills/ 目录下的技能"""
        from bot001.skills.loader import load_skills
        load_skills(self.registry)

    def run(self, session_id: str, user_message: str) -> str:
        """执行一轮用户输入"""
        # 短期记忆：当前对话缓冲
        short_term = ShortTermMemory()
        history = self.long_term.get_messages(session_id)
        for msg in history:
            short_term.add(msg)

        # 长期记忆检索：关键词相关上下文
        relevant = self.long_term.search(user_message, top_k=3)
        mem_context = ""
        if relevant:
            snippets = []
            for msg, score in relevant:
                snippet = msg.content[:200]
                snippets.append(f"- [{msg.role}] {snippet}")
            mem_context = "Related past:\n" + "\n".join(snippets)

        # 保存用户消息
        user_msg = Message(role="user", content=user_message)
        short_term.add(user_msg)
        self.long_term.save_message(session_id, user_msg)

        # 构建消息列表
        messages = [{"role": "system", "content": self.config.system_prompt}]
        if mem_context:
            messages.append({"role": "system", "content": mem_context})
        for msg in short_term.get():
            messages.append(msg.to_dict())

        # ReAct 循环
        tools = self.registry.get_schemas()
        for turn in range(self.config.max_turns):
            response = self.llm.chat(messages, tools)
            choice = response["choices"][0]["message"]

            assistant_msg = Message(
                role="assistant",
                content=choice.get("content", ""),
                tool_calls=[
                    ToolCall(id=tc["id"], name=tc["function"]["name"], arguments=json.loads(tc["function"].get("arguments", "{}")))
                    for tc in choice.get("tool_calls", [])
                ] or None,
            )

            short_term.add(assistant_msg)
            self.long_term.save_message(session_id, assistant_msg)

            messages.append({
                "role": "assistant",
                "content": assistant_msg.content,
                **({"tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}} for tc in assistant_msg.tool_calls]} if assistant_msg.tool_calls else {}),
            })

            if not choice.get("tool_calls"):
                return assistant_msg.content

            for tc in choice["tool_calls"]:
                call_id = tc["id"]
                func_name = tc["function"]["name"]
                try:
                    arguments = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                tool_call = ToolCall(id=call_id, name=func_name, arguments=arguments)
                result = self.executor.execute(tool_call)

                tool_msg = Message(
                    role="tool",
                    content=result.content,
                    name=func_name,
                    tool_call_id=call_id,
                    metadata={"is_error": result.is_error},
                )
                short_term.add(tool_msg)
                self.long_term.save_message(session_id, tool_msg)
                messages.append({
                    "role": "tool",
                    "content": result.content,
                    "tool_call_id": call_id,
                    "name": func_name,
                })

        return "I've reached the maximum number of tool calls. Please refine your request."
