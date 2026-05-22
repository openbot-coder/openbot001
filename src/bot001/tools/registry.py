"""工具注册表"""

from __future__ import annotations

import inspect
import json
from typing import Any, Callable

from bot001.message import ToolCall, ToolResult


class Tool:
    """工具描述"""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: dict[str, Any],
    ):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters

    def to_schema(self) -> dict[str, Any]:
        """转为 JSON Schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def call(self, arguments: dict[str, Any]) -> ToolResult:
        """执行工具"""
        try:
            result = self.func(**arguments)
            return ToolResult(
                tool_call_id="",
                name=self.name,
                content=str(result),
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                name=self.name,
                content=f"Error: {e}",
                is_error=True,
            )


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """列出所有工具"""
        return list(self._tools.values())

    def get_schemas(self) -> list[dict[str, Any]]:
        """获取所有工具的 JSON Schema"""
        return [t.to_schema() for t in self._tools.values()]


def tool_schema(func: Callable) -> dict[str, Any]:
    """从函数签名生成 JSON Schema"""
    sig = inspect.signature(func)
    properties = {}
    required = []

    for name, param in sig.parameters.items():
        if param.annotation == str:
            prop = {"type": "string"}
        elif param.annotation == int:
            prop = {"type": "integer"}
        elif param.annotation == float:
            prop = {"type": "number"}
        elif param.annotation == bool:
            prop = {"type": "boolean"}
        else:
            prop = {"type": "string"}

        if param.default == inspect.Parameter.empty:
            required.append(name)
        else:
            prop["default"] = param.default

        properties[name] = prop

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
