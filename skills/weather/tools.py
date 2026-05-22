"""天气技能 - 示例技能"""

from bot001.skills.base import Skill
from bot001.tools.registry import Tool, tool_schema


def get_weather(city: str = "shenzhen") -> str:
    """查询城市天气（模拟）"""
    data = {
        "shenzhen": "☀️ 28°C, Sunny",
        "beijing": "🌤 22°C, Cloudy",
        "shanghai": "🌧 24°C, Light Rain",
        "guangzhou": "⛅ 30°C, Partly Cloudy",
    }
    return data.get(city.lower(), f"🌍 No data for '{city}'")


class WeatherSkill(Skill):
    name = "weather"
    description = "查询城市天气"

    def get_tools(self):
        return [
            Tool("get_weather", "查询指定城市的当前天气", get_weather, tool_schema(get_weather)),
        ]
