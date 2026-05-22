"""knowledge module tests"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_store_basic(tmp_path):
    from bot001.knowledge.store import WikiStore

    ws = WikiStore(base_dir=str(tmp_path))
    # add source
    sha = ws.add_source("test.md", "# Hello\nContent here")
    assert len(sha) == 16
    assert len(ws.list_sources()) == 1
    # wiki page
    ws.write_page("concepts", "AI", "# AI\n## 关于\n测试内容")
    pages = ws.list_pages("concepts")
    assert len(pages) == 1
    # find by title
    assert ws.find_page("AI") is not None
    assert ws.find_page("Nonexistent") is None
    # index
    ws.update_index_entry("AI", "concept", "concepts")
    assert "[[AI]]" in ws.read_index()
    # log
    ws.append_log("TEST", "hello")
    assert "TEST: hello" in ws.read_log()
    print("✅ store_basic")


def test_wikilinks():
    from bot001.knowledge.store import WikiStore

    ws = WikiStore(base_dir="/tmp/wiki_test_links")
    content = "关联到 [[另一个页面]] 和 [[AI]]"
    links = ws.extract_wikilinks(content)
    assert links == ["另一个页面", "AI"]
    print("✅ wikilinks")


def test_wiki_engine_simple_ingest(tmp_path):
    from bot001.knowledge.store import WikiStore
    from bot001.knowledge.wiki import WikiEngine

    ws = WikiStore(base_dir=str(tmp_path))
    engine = WikiEngine(store=ws, llm=None)  # no LLM
    sha = engine.ingest("test_doc.md", "# Hello\n这是测试内容")
    assert len(sha) == 16
    assert len(ws.list_sources()) == 1
    # simple fallback should create a sources page
    assert len(ws.list_pages("sources")) >= 1
    assert "INGEST_DONE" in ws.read_log()
    print("✅ wiki_engine_simple_ingest")


def test_wiki_engine_query(tmp_path):
    from bot001.knowledge.store import WikiStore
    from bot001.knowledge.wiki import WikiEngine

    ws = WikiStore(base_dir=str(tmp_path))
    # 写入几个页面
    ws.write_page("concepts", "机器学习", "# 机器学习\n## 介绍\n[[深度学习]] 相关内容")
    ws.write_page("concepts", "深度学习", "# 深度学习\n## 介绍\n基于神经网络")
    engine = WikiEngine(store=ws)
    ctx = engine.query("机器学习")
    assert ctx != ""  # 应该匹配到至少一个页面
    print("✅ wiki_engine_query")


def test_wiki_engine_lint(tmp_path):
    from bot001.knowledge.store import WikiStore
    from bot001.knowledge.wiki import WikiEngine

    ws = WikiStore(base_dir=str(tmp_path))
    engine = WikiEngine(store=ws)
    # empty wiki
    issues = engine.lint()
    assert any("空" in i for i in issues)
    # with orphan page
    ws.write_page("concepts", "test", "# test\nno links")
    issues = engine.lint()
    assert any("孤立" in i for i in issues)
    print("✅ wiki_engine_lint")


def test_wiki_engine_llm_ingest(tmp_path):
    """测试有 LLM 回调时的 ingest"""
    from bot001.knowledge.store import WikiStore
    from bot001.knowledge.wiki import WikiEngine

    ws = WikiStore(base_dir=str(tmp_path))

    def mock_llm(system: str, user: str) -> str:
        import json
        return json.dumps({
            "pages": [
                {"subdir": "concepts", "title": "LLM", "content": "## LLM\n大语言模型 [[AI]]", "abstract": "大语言模型"},
                {"subdir": "sources", "title": "source_test", "content": "## 测试文档\n摘要内容", "abstract": "摘要"},
            ],
            "index_entries": ["LLM", "source_test"],
            "log_summary": "添加了 LLM 概念",
        })

    engine = WikiEngine(store=ws, llm=mock_llm)
    sha = engine.ingest("test.md", "# Test\nContent here")
    assert len(ws.list_pages("concepts")) == 1
    assert len(ws.list_pages("sources")) == 1
    assert "[[LLM]]" in ws.read_index()
    print("✅ wiki_engine_llm_ingest")


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_store_basic(Path(td) / "store")
        test_wikilinks()
        test_wiki_engine_simple_ingest(Path(td) / "simple")
        test_wiki_engine_query(Path(td) / "query")
        test_wiki_engine_lint(Path(td) / "lint")
        test_wiki_engine_llm_ingest(Path(td) / "llm")
    print("\n🎉 All knowledge tests passed!")
