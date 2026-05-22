"""bot001 - 轻量级 Console Agent 框架"""

__version__ = "0.1.0"


def create_bot(config_path: str | None = None) -> "Agent":
    """创建 Agent 实例"""
    from bot001.agent import Agent
    from bot001.config import load_config

    config = load_config(config_path)
    return Agent(config)
