"""技能基类"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Skill(ABC):
    """技能基类"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def get_tools(self) -> list:
        """返回该技能提供的工具列表"""
        ...

    def on_load(self) -> None:
        """技能加载时调用"""
        pass

    def on_unload(self) -> None:
        """技能卸载时调用"""
        pass
