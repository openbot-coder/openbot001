"""工具执行器"""

from __future__ import annotations

from bot001.message import ToolCall, ToolResult
from bot001.tools.registry import ToolRegistry


class Executor:
    """工具执行器"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, call: ToolCall) -> ToolResult:
        """执行单个工具调用"""
        tool = self.registry.get(call.name)
        if not tool:
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                content=f"Tool '{call.name}' not found",
                is_error=True,
            )

        result = tool.call(call.arguments)
        result.tool_call_id = call.id
        return result
