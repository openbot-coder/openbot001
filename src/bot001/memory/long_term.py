"""长期记忆 - SQLite 持久化 + 语义检索"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from bot001.message import Message


class LongTermMemory:
    """长期记忆：消息持久化与检索"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages_ltm (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    name TEXT,
                    tool_call_id TEXT,
                    tool_calls TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_ltm_session ON messages_ltm(session_id);
                CREATE INDEX IF NOT EXISTS idx_ltm_created ON messages_ltm(created_at);
            """)
            conn.commit()
        finally:
            conn.close()

    def save_message(self, session_id: str, msg: Message) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO messages_ltm
                   (id, session_id, role, content, name, tool_call_id, tool_calls, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg.id,
                    session_id,
                    msg.role,
                    msg.content,
                    msg.name,
                    msg.tool_call_id,
                    json.dumps([tc.model_dump() for tc in msg.tool_calls]) if msg.tool_calls else "[]",
                    json.dumps(msg.metadata),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_messages(self, session_id: str, limit: int = 200) -> list[Message]:
        """获取会话的所有消息"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM messages_ltm WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()
            return self._rows_to_messages(rows)
        finally:
            conn.close()

    def search(self, query: str, top_k: int = 5) -> list[tuple[Message, float]]:
        """关键词语义检索（基于 TF 打分）"""
        keywords = set(re.findall(r"\w+", query.lower()))
        if not keywords:
            return []

        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM messages_ltm WHERE content != '' AND role IN ('user', 'assistant') ORDER BY created_at DESC"
            ).fetchall()

            scored: list[tuple[Message, float]] = []
            for row in rows:
                text = (row["content"] or "").lower()
                words = set(re.findall(r"\w+", text))
                overlap = len(keywords & words)
                if overlap > 0:
                    score = overlap / max(len(keywords), 1)
                    scored.append((self._row_to_message(row), score))

            scored.sort(key=lambda x: -x[1])
            return scored[:top_k]
        finally:
            conn.close()

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        tool_calls_data = json.loads(row["tool_calls"] or "[]")
        from bot001.message import ToolCall

        return Message(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            name=row["name"],
            tool_call_id=row["tool_call_id"],
            tool_calls=[ToolCall(**tc) for tc in tool_calls_data] or None,
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def _rows_to_messages(self, rows: list[sqlite3.Row]) -> list[Message]:
        return [self._row_to_message(r) for r in rows]
