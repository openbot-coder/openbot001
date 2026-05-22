"""skills module tests"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_skill_base():
    from bot001.skills.base import Skill

    assert hasattr(Skill, "get_tools")
    assert hasattr(Skill, "on_load")
    assert hasattr(Skill, "on_unload")
    print("✅ skill_base")


def test_loader_loads_weather():
    from bot001.tools.registry import ToolRegistry
    from bot001.skills.loader import load_skills

    reg = ToolRegistry()
    loaded = load_skills(reg, skills_dir=str(Path(__file__).parent.parent / "skills"))

    assert "weather" in loaded
    tool = reg.get("get_weather")
    assert tool is not None
    result = tool.call({"city": "shenzhen"})
    assert "28°C" in result.content
    print("✅ loader_loads_weather")


def test_loader_empty_dir(tmp_path):
    from bot001.tools.registry import ToolRegistry
    from bot001.skills.loader import load_skills

    reg = ToolRegistry()
    loaded = load_skills(reg, skills_dir=str(tmp_path))
    assert loaded == []
    print("✅ loader_empty_dir")


def test_parse_skill_md():
    from bot001.skills.loader import parse_skill_md

    skill_dir = Path(__file__).parent.parent / "skills" / "weather"
    info = parse_skill_md(skill_dir)
    assert "name" in info
    assert "weather" in info["name"].lower()
    print("✅ parse_skill_md")


if __name__ == "__main__":
    test_skill_base()
    test_loader_loads_weather()
    test_loader_empty_dir(Path("/tmp/__empty_skill_test__"))
    test_parse_skill_md()
    print("\n🎉 All skills tests passed!")
