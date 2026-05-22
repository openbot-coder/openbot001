"""短期记忆 - 对话缓冲与滑动窗口"""

from __future__ import annotations

from bot001.message import Message


class ShortTermMemory:
    """短期记忆：会话级对话缓冲"""

    def __init__(self, max_messages: int = 20, max_tokens: int = 4000):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self._buffer: list[Message] = []

    def add(self, message: Message) -> None:
        """添加消息到缓冲"""
        self._buffer.append(message)
        self._trim()

    def get(self, limit: int | None = None) -> list[Message]:
        """获取缓冲中的消息"""
        if limit:
            return self._buffer[-limit:]
        return list(self._buffer)

    def clear(self) -> None:
        """清空缓冲"""
        self._buffer.clear()

    def _trim(self) -> None:
        """滑动窗口裁剪"""
        # 按消息数裁剪
        while len(self._buffer) > self.max_messages:
            self._buffer.pop(0)

        # 按 token 估算裁剪
        while self._estimate_tokens() > self.max_tokens and len(self._buffer) > 2:
            self._buffer.pop(0)

    def _estimate_tokens(self) -> int:
        """粗略 token 估算（字符数 / 4）"""
        total = 0
        for msg in self._buffer:
            total += len(msg.content) // 4 + 1
        return total

    def __len__(self) -> int:
        return len(self._buffer)
