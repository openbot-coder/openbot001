"""配置加载"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
import os


@dataclass
class LLMConfig:
    """LLM 配置"""

    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class AgentConfig:
    """Agent 配置"""

    llm: LLMConfig = field(default_factory=LLMConfig)
    max_turns: int = 10
    system_prompt: str = "You are a helpful assistant. Use tools when appropriate."
    work_dir: str = "./data/files"
    db_path: str = "./data/db/bot001.db"


def load_config(config_path: str | None = None) -> AgentConfig:
    """从 .env 和环境变量加载配置"""
    if config_path:
        load_dotenv(config_path)
    else:
        load_dotenv()

    llm = LLMConfig(
        api_base=os.getenv("OPENAI_API_BASE", LLMConfig.api_base),
        api_key=os.getenv("OPENAI_API_KEY", LLMConfig.api_key),
        model=os.getenv("BOT001_MODEL", LLMConfig.model),
        max_tokens=int(os.getenv("BOT001_MAX_TOKENS", str(LLMConfig.max_tokens))),
        temperature=float(os.getenv("BOT001_TEMPERATURE", str(LLMConfig.temperature))),
    )

    return AgentConfig(
        llm=llm,
        max_turns=int(os.getenv("BOT001_MAX_TURNS", "10")),
        work_dir=os.getenv("BOT001_WORK_DIR", "./data/files"),
        db_path=os.getenv("BOT001_DB_PATH", "./data/db/bot001.db"),
    )
