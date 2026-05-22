"""agent tests — ReAct loop with mocked LLM"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json
import os


def _agent_config(tmp_dir=None):
    """创建测试用 AgentConfig"""
    from bot001.config import AgentConfig

    db_dir = tmp_dir or tempfile.mkdtemp()
    db_path = os.path.join(db_dir, "test.db")
    return AgentConfig(
        db_path=db_path,
        system_prompt="你是一个助手",
        max_turns=5,
    )


def test_llm_client_init():
    from bot001.agent import LLMClient
    from bot001.config import LLMConfig

    cfg = LLMConfig(model="gpt-4o-mini", api_base="https://api.openai.com/v1", api_key="test-key")
    client = LLMClient(cfg)
    assert client.model == "gpt-4o-mini"
    assert client.api_base == "https://api.openai.com/v1"
    print("✅ llm_client_init")


def test_llm_client_chat_structure():
    """测试 LLM chat 请求体结构正确"""
    from bot001.agent import LLMClient
    from bot001.config import LLMConfig
    from unittest.mock import patch, MagicMock

    cfg = LLMConfig(model="gpt-4o-mini", api_base="https://api.openai.com/v1", api_key="test-key")
    client = LLMClient(cfg)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "hello", "tool_calls": []}}]
    }

    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.post.return_value = mock_resp
        MockClient.return_value = mock_client

        result = client.chat([{"role": "user", "content": "hi"}])
        assert "choices" in result
        call_args = mock_client.post.call_args
        body = call_args.kwargs["json"]
        assert body["model"] == "gpt-4o-mini"
        assert body["messages"] == [{"role": "user", "content": "hi"}]
        assert "max_tokens" in body
        assert "temperature" in body

    print("✅ llm_client_chat_structure")


def test_llm_client_with_tools():
    from bot001.agent import LLMClient
    from bot001.config import LLMConfig
    from unittest.mock import patch, MagicMock

    cfg = LLMConfig(model="gpt-4o-mini", api_base="https://api.openai.com/v1", api_key="test")
    client = LLMClient(cfg)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {
            "content": "",
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "echo", "arguments": '{"message":"hello"}'}}
            ]
        }}]
    }

    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.post.return_value = mock_resp
        MockClient.return_value = mock_client

        tools = [{"type": "function", "function": {"name": "echo", "parameters": {"type": "object", "properties": {"message": {"type": "string"}}}}}]  # noqa
        result = client.chat([{"role": "user", "content": "hi"}], tools=tools)
        call_args = mock_client.post.call_args
        body = call_args.kwargs["json"]
        assert "tools" in body
        assert body["tool_choice"] == "auto"

    print("✅ llm_client_with_tools")


def test_agent_run_text_response():
    """Agent 收到纯文本回复时直接返回"""
    from bot001.agent import Agent
    from unittest.mock import patch, MagicMock

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            MockClient.return_value = mock_client

            mock_client.post.return_value.json.return_value = {
                "choices": [{"message": {"content": "这是文本回复", "tool_calls": []}}]
            }

            agent = Agent(_agent_config(tmpdir))
            result = agent.run("session_1", "你好")
            assert result == "这是文本回复"
            mock_client.post.assert_called()

    print("✅ agent_run_text_response")


def test_agent_run_tool_call():
    """Agent 收到 tool_call 时执行工具并返回"""
    from bot001.agent import Agent
    from unittest.mock import patch, MagicMock

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            MockClient.return_value = mock_client

            # First call: tool call, second call: text response
            mock_client.post.return_value.json.side_effect = [
                {
                    "choices": [{"message": {
                        "content": "",
                        "tool_calls": [
                            {"id": "call_1", "type": "function", "function": {"name": "echo", "arguments": '{"message":"hello"}'}}
                        ]
                    }}]
                },
                {
                    "choices": [{"message": {"content": "工具执行完成", "tool_calls": []}}]
                }
            ]

            agent = Agent(_agent_config(tmpdir))
            result = agent.run("session_2", "echo hello")
            assert "工具执行完成" in result
            assert mock_client.post.call_count == 2

    print("✅ agent_run_tool_call")


def test_agent_run_max_turns():
    """达到 max_turns 上限时返回提示"""
    from bot001.agent import Agent
    from unittest.mock import patch, MagicMock

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            MockClient.return_value = mock_client

            # Always return tool call
            mock_client.post.return_value.json.return_value = {
                "choices": [{"message": {
                    "content": "",
                    "tool_calls": [
                        {"id": "call_n", "type": "function", "function": {"name": "echo", "arguments": '{"message":"x"}'}}
                    ]
                }}]
            }

            config = _agent_config(tmpdir)
            config.max_turns = 2
            agent = Agent(config)
            result = agent.run("session_3", "repeat")
            assert "maximum" in result.lower() or "refine" in result.lower()
            assert mock_client.post.call_count == 2

    print("✅ agent_run_max_turns")


def test_agent_run_invalid_tool_arguments():
    """工具参数 JSON 解析失败时回退为空 dict"""
    from bot001.agent import Agent
    from unittest.mock import patch, MagicMock

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=None)
            MockClient.return_value = mock_client

            mock_client.post.return_value.json.return_value = {
                "choices": [{"message": {
                    "content": "",
                    "tool_calls": [
                        {"id": "call_bad", "type": "function", "function": {"name": "echo", "arguments": "not json"}}
                    ]
                }}]
            }

            config = _agent_config(tmpdir)
            config.max_turns = 3
            agent = Agent(config)
            result = agent.run("session_4", "bad args")
            # Should fall through to next turn and eventually hit max_turns
            assert mock_client.post.call_count <= 3

    print("✅ agent_run_invalid_tool_arguments")


def test_message_to_dict_tool_calls():
    """Message.to_dict() 包含 tool_calls 时正确序列化"""
    from bot001.message import Message, ToolCall

    tc = ToolCall(id="call_1", name="echo", arguments={"message": "hi"})
    msg = Message(role="assistant", content="", tool_calls=[tc])
    d = msg.to_dict()
    assert "tool_calls" in d
    assert d["tool_calls"][0]["name"] == "echo"
    assert d["tool_calls"][0]["arguments"] == {"message": "hi"}
    print("✅ message_to_dict_tool_calls")


def test_message_to_dict_all_fields():
    """Message.to_dict() 所有可选字段"""
    from bot001.message import Message

    msg = Message(
        role="tool",
        content="result",
        name="echo",
        tool_call_id="call_123",
        metadata={"is_error": False},
    )
    d = msg.to_dict()
    assert d["role"] == "tool"
    assert d["content"] == "result"
    assert d["name"] == "echo"
    assert d["tool_call_id"] == "call_123"
    print("✅ message_to_dict_all_fields")


def test_message_metadata():
    """Message metadata 存取"""
    from bot001.message import Message

    msg = Message(role="user", content="hi", metadata={"key": "value"})
    assert msg.metadata["key"] == "value"
    assert Message(role="assistant", content="").metadata == {}
    print("✅ message_metadata")


if __name__ == "__main__":
    test_llm_client_init()
    test_llm_client_chat_structure()
    test_llm_client_with_tools()
    test_agent_run_text_response()
    test_agent_run_tool_call()
    test_agent_run_max_turns()
    test_agent_run_invalid_tool_arguments()
    test_message_to_dict_tool_calls()
    test_message_to_dict_all_fields()
    test_message_metadata()
    print("\n🎉 All agent tests passed!")
