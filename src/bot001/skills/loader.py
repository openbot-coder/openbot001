"""技能目录加载器"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from bot001.tools.registry import ToolRegistry


def load_skills(registry: ToolRegistry, skills_dir: str = "./skills") -> None:
    """扫描 skills/ 目录并加载技能"""
    base = Path(skills_dir)
    if not base.exists():
        return

    for skill_dir in base.iterdir():
        if not skill_dir.is_dir():
            continue
        tools_file = skill_dir / "tools.py"
        if tools_file.exists():
            _load_skill_module(tools_file, registry)


def _load_skill_module(path: Path, registry: ToolRegistry) -> None:
    """加载单个技能模块"""
    module_name = f"bot001_skill_{path.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
