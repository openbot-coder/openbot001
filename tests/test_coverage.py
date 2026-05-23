"""测试覆盖率补充 - 覆盖所有未测试的代码路径"""

import json
import os
import subprocess
import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bot001 import create_bot
from bot001.config import load_config
from bot001.executor import Executor
from bot001.knowledge.store import WikiStore
from bot001.knowledge.wiki import WikiEngine
from bot001.memory.long_term import LongTermMemory
from bot001.memory.short_term import ShortTermMemory
from bot001.message import Message, ToolCall, ToolResult
from bot001.session import SessionManager
from bot001.skills.base import Skill
from bot001.skills.loader import load_skills, parse_skill_md
from bot001.tools.builtin import (
    SHELL_WHITELIST,
    echo,
    file_read,
    file_write,
    grep,
    shell,
)
from bot001.tools.registry import Tool, ToolRegistry, tool_schema


# ── __init__.py ─────────────────────────────────────────────


def test_create_bot():
    """测试 create_bot 函数"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("OPENAI_API_KEY=sk-test123\n")
        f.write("OPENAI_API_BASE=https://api.test.com/v1\n")
        config_path = f.name

    try:
        with patch("bot001.agent.Agent") as mock_agent:
            mock_agent.return_value = MagicMock()
            bot = create_bot(config_path)
            assert bot is not None
            mock_agent.assert_called_once()
    finally:
        os.unlink(config_path)


# ── config.py ───────────────────────────────────────────────


def test_load_config_file_not_found():
    """测试配置文件不存在时的回退"""
    config = load_config("/nonexistent/path/.env")
    assert config is not None
    # 应该使用环境变量或默认值


# ── executor.py ──────────────────────────────────────────────


def test_executor_tool_not_found():
    """测试执行不存在的工具"""
    registry = ToolRegistry()
    executor = Executor(registry)
    call = ToolCall(name="nonexistent_tool", arguments={})
    result = executor.execute(call)
    assert result.is_error is True
    assert "not found" in result.content.lower()


# ── session.py ──────────────────────────────────────────────


def test_list_sessions():
    """测试列出所有会话"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        mgr = SessionManager(db_path)

        # 创建几个会话
        session1 = mgr.create_session()
        session2 = mgr.create_session()

        sessions = mgr.list_sessions()
        assert len(sessions) == 2
        assert sessions[0]["id"] in [session1, session2]
        assert sessions[1]["id"] in [session1, session2]


def test_session_list_sessions_empty():
    """测试列出空会话列表"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        mgr = SessionManager(db_path)

        sessions = mgr.list_sessions()
        assert sessions == []


# ── memory/short_term.py ────────────────────────────────────


def test_short_term_get_with_limit():
    """测试获取有限数量的消息"""
    stm = ShortTermMemory(max_messages=10)
    for i in range(5):
        stm.add(Message(role="user", content=f"msg {i}"))

    limited = stm.get(limit=2)
    assert len(limited) == 2
    assert limited[0].content == "msg 3"
    assert limited[1].content == "msg 4"


def test_short_term_trim_by_tokens():
    """测试按 token 数裁剪"""
    stm = ShortTermMemory(max_messages=100, max_tokens=10)
    # 添加长消息触发 token 裁剪
    for i in range(5):
        stm.add(Message(role="user", content="x" * 100))

    # 应该裁剪到只剩少量消息
    assert len(stm) <= 3


def test_short_term_clear():
    """测试清空缓冲"""
    stm = ShortTermMemory()
    stm.add(Message(role="user", content="test"))
    assert len(stm) == 1
    stm.clear()
    assert len(stm) == 0


# ── memory/long_term.py ─────────────────────────────────────


def test_long_term_search_empty_query():
    """测试空查询的搜索"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "ltm.db")
        ltm = LongTermMemory(db_path)

        results = ltm.search("")
        assert results == []


def test_long_term_search_no_results():
    """测试搜索无结果"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "ltm.db")
        ltm = LongTermMemory(db_path)

        results = ltm.search("nonexistent_keyword_xyz")
        assert results == []


# ── knowledge/store.py ──────────────────────────────────────


def test_wiki_store_get_source_not_found():
    """测试获取不存在的源文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        result = store.get_source("nonexistent_sha")
        assert result is None


def test_wiki_store_read_page_not_found():
    """测试读取不存在的页面"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        result = store.read_page("wiki", "nonexistent")
        assert result is None


def test_wiki_store_read_log_empty():
    """测试读取空日志"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        log = store.read_log()
        assert log == ""


def test_wiki_store_resolve_wikilink_not_found():
    """测试解析不存在的 wikilink"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        result = store.resolve_wikilink("nonexistent")
        assert result is None


def test_wiki_store_resolve_wikilink_exists():
    """测试解析存在的 wikilink"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        store.write_page("concepts", "test_page", "test content")

        result = store.resolve_wikilink("test_page")
        assert result == "test content"


def test_wiki_engine_ingest_with_no_json_in_result():
    """测试 ingest 处理 LLM 返回中没有 JSON 格式的情况"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        engine = WikiEngine(store)

        def mock_llm(**kwargs):
            return "这是纯文本结果，没有 JSON 代码块"

        engine._llm = mock_llm
        sha = engine.ingest("test_doc", "some content")
        assert sha is not None


def test_session_list_sessions_with_data():
    """测试列出有数据的会话"""
    import json
    from bot001.session import SessionManager

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        mgr = SessionManager(db_path)
        session_id = mgr.create_session()

        # 添加一条消息，触发 tool_calls 和 messages 重建
        mgr.save_message(
            session_id,
            Message(role="assistant", content="test", tool_calls=[]),
        )

        # 列出会话，会触发 messages.count() > 0 和其他路径
        sessions = mgr.list_sessions()
        assert len(sessions) >= 1


def test_session_get_messages_with_tool_calls():
    """测试获取带 tool_calls 的消息"""
    from bot001.session import SessionManager

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        mgr = SessionManager(db_path)
        session_id = mgr.create_session()

        # 添加带 tool_calls 的消息
        msg = Message(
            role="assistant",
            content="test",
            tool_calls=[ToolCall(name="test_tool", arguments={"x": 1})],
        )
        mgr.save_message(session_id, msg)

        # 获取消息，触发 ToolCall 解析路径
        msgs = mgr.get_messages(session_id)
        assert len(msgs) == 1
        assert msgs[0].tool_calls is not None
        assert len(msgs[0].tool_calls) == 1
        assert msgs[0].tool_calls[0].name == "test_tool"


def test_loader_skill_with_error():
    """测试加载有错误的技能模块"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "bad_skill"
        skill_dir.mkdir()
        (skill_dir / "tools.py").write_text("import nonexistent_module\n")
        (skill_dir / "SKILL.md").write_text("# Bad Skill\n")

        registry = ToolRegistry()
        skills = load_skills(registry, tmpdir)
        assert len(skills) == 0


def test_import_skill_module_invalid_spec():
    """测试 spec.loader 为 None 的情况"""
    from bot001.skills.loader import _import_skill_module

    with patch("importlib.util.spec_from_file_location") as mock_spec:
        # 模拟 spec_from_file_location 返回 spec 但 spec.loader 为 None
        mock_spec_obj = MagicMock()
        mock_spec_obj.loader = None
        mock_spec.return_value = mock_spec_obj

        with pytest.raises(ImportError, match="Cannot load spec"):
            _import_skill_module(Path("/some/path.py"), "test_bad")


def test_wiki_store_list_pages():
    """测试列出所有页面"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        store.write_page("concepts", "test_page", "content")
        pages = store.list_pages()
        assert len(pages) == 1


def test_wiki_store_list_pages_with_subdir():
    """测试列出指定子目录的页面"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        store.write_page("concepts", "test1", "content1")
        store.write_page("entities", "test2", "content2")

        concept_pages = store.list_pages("concepts")
        assert len(concept_pages) == 1
        assert "test1" in str(concept_pages[0])


# ── knowledge/wiki.py ───────────────────────────────────────


def test_wiki_engine_ingest_invalid_json():
    """测试 ingest 处理无效 JSON - 格式正确但内容无效"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        engine = WikiEngine(store)

        # 模拟 LLM 返回格式正确但内容无效的 JSON
        def mock_llm(**kwargs):
            return "```json\n{invalid json content}\n```"

        engine._llm = mock_llm
        sha = engine.ingest("test_doc", "some content")
        assert sha is not None


def test_wiki_engine_ingest_malformed_json():
    """测试 ingest 处理格式错误的 JSON"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        engine = WikiEngine(store)

        def mock_llm(**kwargs):
            return "{ invalid json }"

        engine._llm = mock_llm
        sha = engine.ingest("test_doc", "some content")
        assert sha is not None


def test_wiki_engine_lint_empty_wiki():
    """测试 lint 空 wiki"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        engine = WikiEngine(store)

        issues = engine.lint()
        assert len(issues) > 0
        assert "为空" in str(issues[0])


def test_wiki_engine_lint_orphan_page():
    """测试 lint 检测孤立页面"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        engine = WikiEngine(store)

        # 创建一个无引用的页面
        store.write_page("concepts", "orphan_page", "content")

        issues = engine.lint()
        # 应该有孤立页面警告
        assert any("孤立" in str(i) for i in issues)


def test_wiki_engine_query_no_results():
    """测试查询无结果"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        engine = WikiEngine(store)

        result = engine.query("nonexistent_keyword_xyz")
        assert result == ""


# ── skills/base.py ──────────────────────────────────────────


class TestSkill(Skill):
    """测试用技能"""

    name = "test_skill"
    description = "测试技能"

    def get_tools(self) -> list:
        return []


def test_skill_on_load_unload():
    """测试技能生命周期方法"""
    skill = TestSkill()
    # 应该不抛出异常
    skill.on_load()
    skill.on_unload()


# ── skills/loader.py ────────────────────────────────────────


def test_load_skills_empty_dir():
    """测试加载空目录的技能"""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ToolRegistry()
        skills = load_skills(registry, tmpdir)
        assert skills == []


def test_load_skills_no_tools_py():
    """测试加载没有 tools.py 的目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test_skill"
        skill_dir.mkdir()
        # 不创建 tools.py

        registry = ToolRegistry()
        skills = load_skills(registry, tmpdir)
        assert skills == []


def test_parse_skill_md_not_exists():
    """测试解析不存在的 SKILL.md"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test"
        skill_dir.mkdir()
        info = parse_skill_md(skill_dir)
        assert info == {}


def test_parse_skill_md():
    """测试解析 SKILL.md"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test"
        skill_dir.mkdir()
        md_file = skill_dir / "SKILL.md"
        md_file.write_text("# Test Skill\n## Usage\nAuthor: test\n")

        info = parse_skill_md(skill_dir)
        assert info.get("name") == "Test Skill"
        assert "Usage" in info.get("sections", [])
        assert info.get("author") == "test"


# ── tools/builtin.py ────────────────────────────────────────


def test_echo():
    """测试 echo"""
    assert echo("hello") == "hello"


def test_grep_file_not_found():
    """测试 grep 文件不存在"""
    result = grep("pattern", "/nonexistent/path")
    assert "not found" in result.lower()


def test_grep_error():
    """测试 grep 异常处理"""
    with patch("pathlib.Path.exists", side_effect=Exception("test error")):
        result = grep("pattern", ".")
        assert "error" in result.lower()


def test_shell_not_in_whitelist():
    """测试 shell 命令不在白名单"""
    result = shell("rm -rf /")
    assert "not in whitelist" in result


def test_shell_timeout():
    """测试 shell 命令超时"""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
        result = shell("ls")
        assert "timed out" in result.lower()


def test_shell_error():
    """测试 shell 命令异常"""
    with patch("subprocess.run", side_effect=Exception("test error")):
        result = shell("ls")
        assert "error" in result.lower()


def test_file_read_not_found():
    """测试读取不存在的文件"""
    result = file_read("/nonexistent/file.txt")
    assert "not found" in result.lower()


def test_file_read_error():
    """测试读取文件异常"""
    # 先创建文件，这样 exists 检查通过但 read_text 抛出异常
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmpfile = f.name

    try:
        with patch("pathlib.Path.read_text", side_effect=Exception("test error")):
            # 需要 patch 对应的路径
            with patch("pathlib.Path.exists", return_value=True):
                result = file_read(tmpfile)
            assert "error" in result.lower()
    finally:
        os.unlink(tmpfile)


def test_file_write_error():
    """测试写入文件异常"""
    with patch("pathlib.Path.write_text", side_effect=Exception("test error")):
        result = file_write("/tmp/test.txt", "content")
        assert "error" in result.lower()


# ── tools/registry.py ───────────────────────────────────────


def test_tool_call_error():
    """测试工具调用异常"""

    def failing_func(x: int) -> int:
        raise ValueError("test error")

    tool = Tool("failing", "test", failing_func, {"type": "object", "properties": {}})
    result = tool.call({"x": 1})
    assert result.is_error is True
    assert "error" in result.content.lower()


def test_tool_schema_int():
    """测试 tool_schema 处理 int 类型"""

    def func(x: int, y: float, z: bool, s: str = "default") -> None:
        pass

    schema = tool_schema(func)
    assert schema["properties"]["x"]["type"] == "integer"
    assert schema["properties"]["y"]["type"] == "number"
    assert schema["properties"]["z"]["type"] == "boolean"
    assert "default" in schema["properties"]["s"]


def test_tool_schema_default():
    """测试 tool_schema 处理默认值"""

    def func(required_param: str, optional_param: str = "default") -> None:
        pass

    schema = tool_schema(func)
    assert "required_param" in schema["required"]
    assert "optional_param" not in schema["required"]
    assert schema["properties"]["optional_param"]["default"] == "default"


def test_registry_get():
    """测试获取工具"""
    registry = ToolRegistry()
    tool = Tool("test", "test desc", lambda: None, {})
    registry.register(tool)

    retrieved = registry.get("test")
    assert retrieved is tool

    not_found = registry.get("nonexistent")
    assert not_found is None


def test_registry_list_tools():
    """测试列出所有工具"""
    registry = ToolRegistry()
    registry.register(Tool("t1", "desc1", lambda: None, {}))
    registry.register(Tool("t2", "desc2", lambda: None, {}))

    tools = registry.list_tools()
    assert len(tools) == 2


def test_registry_get_schemas():
    """测试获取工具 schema"""
    registry = ToolRegistry()
    registry.register(Tool("test", "desc", lambda: None, {}))

    schemas = registry.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "test"


# ── message.py ──────────────────────────────────────────────


def test_message_to_dict():
    """测试 Message 转 dict"""
    msg = Message(
        role="assistant",
        content="test",
        name="bot",
        tool_call_id="call_123",
        tool_calls=[ToolCall(name="test", arguments={})],
    )
    d = msg.to_dict()
    assert d["role"] == "assistant"
    assert d["content"] == "test"
    assert d["name"] == "bot"
    assert d["tool_call_id"] == "call_123"
    assert "tool_calls" in d


def test_message_to_dict_minimal():
    """测试最小 Message 转 dict"""
    msg = Message(role="user", content="hello")
    d = msg.to_dict()
    assert d == {"role": "user", "content": "hello"}


def test_tool_result():
    """测试 ToolResult"""
    result = ToolResult(tool_call_id="call_1", name="test", content="ok", is_error=False)
    assert result.is_error is False
    assert result.content == "ok"


# ── agent.py ────────────────────────────────────────────────


def test_safe_json_invalid():
    """测试 _safe_json 处理无效 JSON"""
    from bot001.agent import _safe_json

    result = _safe_json("not json")
    assert result == {}

    result = _safe_json("{invalid}")
    assert result == {}

    result = _safe_json(None)
    assert result == {}


def test_agent_with_memory_context():
    """测试 agent 使用长期记忆上下文"""
    from bot001.agent import Agent
    from bot001.config import AgentConfig
    from bot001.message import Message

    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("OPENAI_API_KEY=sk-test\n")
        f.write("OPENAI_API_BASE=https://api.test.com/v1\n")
        config_path = f.name

    try:
        config = load_config(config_path)
        config.max_turns = 1
        agent = Agent(config)
        session_id = agent.session_manager.create_session()

        # 模拟 LLM 返回无 tool_calls 的响应
        def mock_chat(messages, tools):
            return {"choices": [{"message": {"content": "Hello!", "tool_calls": []}}]}

        agent.llm.chat = mock_chat

        # 先保存一些历史消息到长期记忆
        agent.long_term.save_message(session_id, Message(role="user", content="previous query about python"))
        agent.long_term.save_message(session_id, Message(role="assistant", content="Python is great"))

        # 运行 agent，应该触发长期记忆检索
        result = agent.run(session_id, "tell me about python")
        assert result is not None
    finally:
        os.unlink(config_path)


def test_agent_with_tool_call_no_arguments():
    """测试 agent 处理无参数的 tool call"""
    from bot001.agent import Agent

    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("OPENAI_API_KEY=sk-test\n")
        f.write("OPENAI_API_BASE=https://api.test.com/v1\n")
        config_path = f.name

    try:
        config = load_config(config_path)
        config.max_turns = 1
        agent = Agent(config)
        session_id = agent.session_manager.create_session()

        def mock_chat(messages, tools):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "echo",
                                        "arguments": '{"text": "hello"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

        agent.llm.chat = mock_chat

        result = agent.run(session_id, "test echo")
        assert result is not None
    finally:
        os.unlink(config_path)


# ── Additional coverage for remaining gaps ───────────────────


def test_wiki_store_get_source_exists():
    """测试 get_source 当文件存在时"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        import re
        # 创建一个源文件，使用正确的命名模式
        sha = "test_sha_123"
        safe_name = re.sub(r"[^\w\-]", "_", "test_doc")
        source_path = store.sources_dir / f"{safe_name}_{sha}.md"
        source_path.write_text("content")

        result = store.get_source(sha)
        assert result is not None
        assert result.exists()


def test_wiki_store_read_page_exists():
    """测试 read_page 当页面存在时"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        store.write_page("concepts", "test_page", "test content")

        content = store.read_page("concepts", "test_page")
        assert content == "test content"


def test_wiki_engine_query_with_wikilink():
    """测试 query 解析 wikilink"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        engine = WikiEngine(store)

        # 创建页面和引用
        store.write_page("concepts", "main", "This references [[related]]")
        store.write_page("concepts", "related", "Related content")

        result = engine.query("main")
        assert "main" in result
        assert "related" in result


def test_wiki_engine_lint_broken_link():
    """测试 lint 检测破损链接"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = WikiStore(tmpdir)
        engine = WikiEngine(store)

        # 创建有破损链接的页面
        store.write_page("concepts", "broken", "This has [[nonexistent]] link")

        issues = engine.lint()
        assert any("破损" in str(i) for i in issues)


def test_load_skills_base_not_exists():
    """测试加载不存在的技能目录"""
    registry = ToolRegistry()
    skills = load_skills(registry, "/nonexistent/path")
    assert skills == []


def test_load_skills_hidden_dir():
    """测试加载隐藏目录的技能（应该跳过）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        # 创建以 _ 开头的目录
        hidden_dir = base / "_hidden_skill"
        hidden_dir.mkdir()
        (hidden_dir / "tools.py").write_text(
            "from bot001.skills.base import Skill\n"
            "from bot001.tools.registry import Tool, ToolRegistry\n"
        )

        registry = ToolRegistry()
        skills = load_skills(registry, tmpdir)
        # 隐藏目录应该被跳过
        assert len(skills) == 0

        # 测试以 . 开头的目录
        dot_dir = base / ".dot_skill"
        dot_dir.mkdir()

        skills = load_skills(registry, tmpdir)
        assert len(skills) == 0


def test_load_skills_no_skill_class():
    """测试加载没有 Skill 子类但有 Tool 对象的 tools.py"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "test_skill"
        skill_dir.mkdir()
        # 创建 tools.py 有 Tool 对象但没有 Skill 子类
        (skill_dir / "tools.py").write_text(
            "from bot001.tools.registry import Tool\n"
            "def my_func(): pass\n"
            "test_tool = Tool('test', 'desc', my_func, {'type': 'object', 'properties': {}})\n"
        )
        (skill_dir / "SKILL.md").write_text("# Test\n")

        registry = ToolRegistry()
        skills = load_skills(registry, tmpdir)
        # 应该加载成功并注册工具
        assert len(skills) == 1
        assert registry.get("test") is not None


def test_load_skills_error_handling():
    """测试加载技能时发生异常"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "bad_skill"
        skill_dir.mkdir()
        # 创建有语法错误的 tools.py
        (skill_dir / "tools.py").write_text("this is invalid python syntax @@@")
        (skill_dir / "SKILL.md").write_text("# Bad Skill\n")

        registry = ToolRegistry()
        # 应该捕获异常而不会崩溃
        skills = load_skills(registry, tmpdir)
        assert len(skills) == 0


def test_grep_exception_handling():
    """测试 grep 异常处理覆盖"""
    with patch("pathlib.Path.exists", side_effect=Exception("grep error")):
        result = grep("pattern", ".")
        assert "error" in result.lower()


def test_shell_stderr_handling():
    """测试 shell 处理 stderr"""
    # 使用一个会产生 stderr 的命令
    result = shell("ls /nonexistent_path_12345")
    assert "stderr" in result.lower() or "error" in result.lower()


def test_shell_timeout_handling():
    """测试 shell 超时处理"""
    # 已经在 test_shell_timeout 中测试
    pass


def test_shell_timeout_expired():
    """测试 shell 超时异常处理"""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
        result = shell("ls")
        assert "timed out" in result.lower()


def test_grep_exception_in_file_read():
    """测试 grep 文件读取异常"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建一个文件
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("test content")

        # 让 read_text 失败，应该被 except Exception: pass 捕获
        with patch("pathlib.Path.read_text", side_effect=Exception("read error")):
            result = grep("test", tmpdir)
            # 应该返回 Found 0 files 因为所有文件读取都失败了
            assert "Found" in result


# ── console.py ──────────────────────────────────────────────


def test_console_print_welcome():
    """测试 print_welcome 函数"""
    from bot001.console import print_welcome

    print_welcome()


def test_console_print_help():
    """测试 print_help 函数"""
    from bot001.console import print_help

    print_help()


def test_console_print_response():
    """测试 print_response 函数"""
    from io import StringIO
    from bot001.console import print_response

    with patch("sys.stdout", new_callable=StringIO):
        print_response("test response")


def _run_console_with_inputs(inputs_text):
    """运行 console main 的辅助函数"""
    from io import StringIO
    import sys
    from bot001.console import main

    inputs = StringIO(inputs_text)
    original_stdin = sys.stdin
    sys.stdin = inputs
    try:
        with patch("bot001.console.Agent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            mock_agent.session_manager.create_session.return_value = "test-session-123"
            main()
    except SystemExit:
        pass
    finally:
        sys.stdin = original_stdin


def test_console_main_exit():
    """测试 console main 退出"""
    _run_console_with_inputs("/help\n/exit\n")


def test_console_main_new_session():
    """测试 console main 创建新会话"""
    _run_console_with_inputs("/new\n/exit\n")


def test_console_main_list_sessions():
    """测试 console main 列出会话"""
    _run_console_with_inputs("/list\n/exit\n")


def test_console_main_delete_session():
    """测试 console main 删除会话"""
    _run_console_with_inputs("/delete invalid_session\n/exit\n")


def test_console_main_delete_current_session():
    """测试 console main 删除当前会话"""
    from io import StringIO
    import sys
    from bot001.console import main

    # 先 /new 创建会话获取 session_id，然后删除当前 session
    inputs = StringIO("/new\n/delete test-session-123\n/exit\n")
    original_stdin = sys.stdin
    sys.stdin = inputs
    try:
        with patch("bot001.console.Agent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            mock_agent.session_manager.create_session.return_value = "test-session-123"
            main()
    except SystemExit:
        pass
    finally:
        sys.stdin = original_stdin


def test_console_main_delete_other_session():
    """测试 console main 删除其他会话"""
    from io import StringIO
    import sys
    from bot001.console import main

    inputs = StringIO("/delete other-session\n/exit\n")
    original_stdin = sys.stdin
    sys.stdin = inputs
    try:
        with patch("bot001.console.Agent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            mock_agent.session_manager.create_session.return_value = "test-session-123"
            main()
    except SystemExit:
        pass
    finally:
        sys.stdin = original_stdin


def test_console_main_list_sessions_with_data():
    """测试 console main 列出会话（有数据）"""
    from io import StringIO
    import sys
    from bot001.console import main

    inputs = StringIO("/list\n/exit\n")
    original_stdin = sys.stdin
    sys.stdin = inputs
    try:
        with patch("bot001.console.Agent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            mock_agent.session_manager.create_session.return_value = "test-session-123"
            mock_agent.session_manager.list_sessions.return_value = [
                {"id": "s1", "updated_at": "2026-01-01"},
                {"id": "s2", "updated_at": "2026-01-02"},
            ]
            main()
    except SystemExit:
        pass
    finally:
        sys.stdin = original_stdin


def test_console_main_run_agent():
    """测试 console main 运行 agent"""
    from io import StringIO
    import sys
    from bot001.console import main

    inputs = StringIO("hello\n/exit\n")
    original_stdin = sys.stdin
    sys.stdin = inputs
    try:
        with patch("bot001.console.Agent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            mock_agent.session_manager.create_session.return_value = "test-session-123"
            mock_agent.run.return_value = "Hello! How can I help?"
            main()
    except SystemExit:
        pass
    finally:
        sys.stdin = original_stdin


def test_console_main_unknown_command():
    """测试 console main 处理未知命令"""
    _run_console_with_inputs("/unknown_cmd\n/exit\n")


def test_console_main_empty_input():
    """测试 console main 处理空输入"""
    _run_console_with_inputs("\n\n/exit\n")


def test_console_main_eof():
    """测试 console main 处理 EOF"""
    from io import StringIO
    import sys
    from bot001.console import main

    inputs = StringIO("")
    original_stdin = sys.stdin
    sys.stdin = inputs
    try:
        with patch("bot001.console.Agent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            mock_agent.session_manager.create_session.return_value = "test-session-123"
            main()
    except (SystemExit, EOFError):
        pass
    finally:
        sys.stdin = original_stdin


def test_console_module_main():
    """测试 console 模块的 __main__ 入口 — 用 runpy 模拟 __main__ 执行"""
    import runpy, sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    # 切换到执行目录
    orig_cwd = os.getcwd()
    os.chdir(os.path.join(os.path.dirname(__file__), '..'))
    try:
        # 用 runpy 模拟 python -m bot001.console
        # 这会触发 if __name__ == "__main__": main()
        import io
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("/exit\n")
        try:
            runpy.run_module("bot001.console", run_name="__main__")
        except (SystemExit, EOFError):
            pass
        finally:
            sys.stdin = old_stdin
    finally:
        os.chdir(orig_cwd)
