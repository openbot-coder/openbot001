"""会话管理 (SQLite)"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bot001.message import Message


class SessionManager:
    """SQLite 会话管理"""

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
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    state TEXT DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    name TEXT,
                    tool_call_id TEXT,
                    tool_calls TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def create_session(self) -> str:
        """创建新会话"""
        session_id = uuid4().hex[:16]
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO sessions (id) VALUES (?)",
                (session_id,),
            )
            conn.commit()
            return session_id
        finally:
            conn.close()

    def session_exists(self, session_id: str) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def save_message(self, session_id: str, msg: Message) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO messages (id, session_id, role, content, name, tool_call_id, tool_calls, metadata)
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
            conn.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_messages(self, session_id: str, limit: int = 100) -> list[Message]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()

            msgs = []
            for row in rows:
                tool_calls_data = json.loads(row["tool_calls"] or "[]")
                tool_calls = []
                for tc in tool_calls_data:
                    from bot001.message import ToolCall
                    tool_calls.append(ToolCall(**tc))

                msgs.append(Message(
                    id=row["id"],
                    role=row["role"],
                    content=row["content"],
                    name=row["name"],
                    tool_call_id=row["tool_call_id"],
                    tool_calls=tool_calls or None,
                    metadata=json.loads(row["metadata"] or "{}"),
                ))
            return msgs
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> None:
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
        finally:
            conn.close()

    def list_sessions(self) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
