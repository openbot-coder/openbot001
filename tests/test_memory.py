"""memory module tests"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_short_term():
    from bot001.memory.short_term import ShortTermMemory
    from bot001.message import Message

    mem = ShortTermMemory(max_messages=3)
    assert len(mem) == 0

    for i in range(5):
        mem.add(Message(role="user", content=f"msg{i}"))
    assert len(mem) == 3  # 滑动窗口
    assert mem.get()[0].content == "msg2"

    mem.clear()
    assert len(mem) == 0
    print("✅ short_term")


def test_long_term_save_and_retrieve():
    from bot001.memory.long_term import LongTermMemory
    from bot001.message import Message

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/ltm.db"
        ltm = LongTermMemory(db_path)

        msg = Message(role="user", content="hello world")
        ltm.save_message("sid1", msg)

        msgs = ltm.get_messages("sid1")
        assert len(msgs) == 1
        assert msgs[0].content == "hello world"
        assert msgs[0].role == "user"

        # 不同会话
        msgs2 = ltm.get_messages("sid2")
        assert len(msgs2) == 0
    print("✅ long_term save/retrieve")


def test_long_term_search():
    from bot001.memory.long_term import LongTermMemory
    from bot001.message import Message

    with tempfile.TemporaryDirectory() as tmpdir:
        ltm = LongTermMemory(f"{tmpdir}/ltm.db")

        for text in ["stock market rally", "weather forecast", "AI agent framework", "python coding tips"]:
            ltm.save_message("sid1", Message(role="user", content=text))

        results = ltm.search("python code", top_k=2)
        assert len(results) > 0
        best = results[0]
        assert "python" in best[0].content or "code" in best[0].content
    print("✅ long_term search")


def test_agent_memory_integration():
    """验证 Agent 创建时正确初始化记忆系统"""
    import tempfile
    from bot001.config import AgentConfig
    from bot001.agent import Agent

    config = AgentConfig(db_path="/tmp/__test_agent_mem__.db")
    agent = Agent(config)
    assert agent.long_term is not None
    assert agent.session_manager is not None
    print("✅ agent memory integration")


if __name__ == "__main__":
    test_short_term()
    test_long_term_save_and_retrieve()
    test_long_term_search()
    test_agent_memory_integration()
    print("\n🎉 All memory tests passed!")
