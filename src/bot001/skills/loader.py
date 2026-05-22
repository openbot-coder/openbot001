"""技能加载器"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from bot001.skills.base import Skill

if TYPE_CHECKING:
    from bot001.tools.registry import ToolRegistry


def load_skills(registry: "ToolRegistry", skills_dir: str = "./skills") -> list[str]:
    """扫描 skills/ 目录并加载技能，返回加载的技能名列表"""
    base = Path(skills_dir)
    if not base.exists():
        return []

    loaded = []
    for skill_dir in base.iterdir():
        if not skill_dir.is_dir():
            continue
        if skill_dir.name.startswith("_") or skill_dir.name.startswith("."):
            continue

        # 查找 tools.py
        tools_file = skill_dir / "tools.py"
        if not tools_file.exists():
            continue

        skill_name = skill_dir.name
        try:
            module = _import_skill_module(tools_file, skill_name)

            # 查找 Skill 子类
            skill_cls = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Skill) and attr is not Skill:
                    skill_cls = attr
                    break

            if skill_cls:
                skill_instance: Skill = skill_cls()
                skill_instance.on_load()

                # 注册该技能提供的工具
                for tool in skill_instance.get_tools():
                    registry.register(tool)

                loaded.append(skill_name)
            else:
                # 无 Skill 子类时，尝试直接从模块注册 Tool 对象
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if hasattr(attr, "name") and hasattr(attr, "call"):
                        registry.register(attr)
                loaded.append(skill_name)

        except Exception as e:
            print(f"[bot001] Failed to load skill '{skill_name}': {e}")

    return loaded


def _import_skill_module(path: Path, module_name: str):
    """动态导入技能模块"""
    full_name = f"bot001_skills_{module_name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def parse_skill_md(skill_dir: Path) -> dict:
    """解析 SKILL.md 返回元信息"""
    md_file = skill_dir / "SKILL.md"
    if not md_file.exists():
        return {}

    content = md_file.read_text()
    info = {}

    for line in content.splitlines():
        if line.startswith("# "):
            info["name"] = line[2:].strip()
        elif line.startswith("## "):
            info.setdefault("sections", []).append(line[3:].strip())
        elif ":" in line and not line.startswith("-"):
            key, _, val = line.partition(":")
            info[key.strip().lower()] = val.strip()

    return info
