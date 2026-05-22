"""smoke test - bot001 v0.1.0"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_message():
    from bot001.message import Message, ToolCall

    m = Message(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"
    assert m.id  # auto-generated

    tc = ToolCall(name="echo", arguments={"message": "hi"})
    assert tc.name == "echo"
    print("✅ message")


def test_config():
    from bot001.config import load_config

    config = load_config()
    assert config.llm.model
    assert config.llm.api_base
    print("✅ config")


def test_registry():
    from bot001.tools.registry import ToolRegistry, Tool
    from bot001.tools.builtin import register_builtin_tools

    reg = ToolRegistry()
    register_builtin_tools(reg)

    assert len(reg.list_tools()) >= 5
    assert reg.get("echo") is not None

    tool = reg.get("echo")
    result = tool.call({"message": "test"})
    assert "test" in result.content
    print("✅ registry")


def test_executor():
    from bot001.tools.registry import ToolRegistry
    from bot001.tools.builtin import register_builtin_tools
    from bot001.executor import Executor
    from bot001.message import ToolCall

    reg = ToolRegistry()
    register_builtin_tools(reg)
    executor = Executor(reg)

    tc = ToolCall(name="echo", arguments={"message": "hello"})
    result = executor.execute(tc)
    assert result.content == "hello"
    assert not result.is_error
    print("✅ executor")


def test_session():
    import tempfile
    from bot001.session import SessionManager
    from bot001.message import Message

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        sm = SessionManager(db_path)

        sid = sm.create_session()
        assert sm.session_exists(sid)

        msg = Message(role="user", content="hi")
        sm.save_message(sid, msg)

        msgs = sm.get_messages(sid)
        assert len(msgs) == 1
        assert msgs[0].content == "hi"

        sm.delete_session(sid)
        assert not sm.session_exists(sid)
    print("✅ session")


if __name__ == "__main__":
    test_message()
    test_config()
    test_registry()
    test_executor()
    test_session()
    print("\n🎉 All smoke tests passed!")
