"""消息模型"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Message(BaseModel):
    """对话消息"""

    id: str = Field(default_factory=lambda: uuid4().hex)
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转为 API 格式"""
        d = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = [tc.model_dump() for tc in self.tool_calls]
        return d


class ToolCall(BaseModel):
    """工具调用请求"""

    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """工具执行结果"""

    tool_call_id: str
    name: str
    content: str
    is_error: bool = False
