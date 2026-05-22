"""知识库核心流程 — Ingest / Query / Lint"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from bot001.knowledge.store import WikiStore

# LLM 补全函数签名：接受 system/user prompt，返回字符串
LLMFunc = Callable[..., str]


class WikiEngine:
    """LLM Wiki 风格的知识库引擎

    三步核心操作:
    - ingest:  分析原始文档 → 生成 wiki 页面
    - query:   检索 wiki → 返回相关上下文
    - lint:    审查 wiki 完整性 → 推荐行动
    """

    INGEST_PROMPT = """你是一个知识库管理员。分析下面的原始文档，生成符合以下规范的 wiki 页面。

## 输出要求 (JSON 格式，只输出 JSON，不加注释说明)

```json
{
  "pages": [
    {
      "subdir": "entities" | "concepts" | "sources",
      "title": "页面标题",
      "content": "## 页面内容，支持 [[wikilink]] 交叉引用\\n可以使用 YAML frontmatter\\n",
      "abstract": "一句话摘要"
    }
  ],
  "index_entries": ["页面标题1", "页面标题2"],
  "log_summary": "简短的日志描述"
}
```

## 规范
- YAML frontmatter: 包含 type, title, sources[]
- [[wikilink]]: 关联到其他 wiki 页面
- 至少产生: 1 个 source 摘要 + 1+ 个 entity/concept 页面
- 用中文输出
"""

    QUERY_PROMPT = """从以下 wiki 内容中提取与查询最相关的信息来回答问题。
如果有 [[wikilink]] 标记的页面涉及相关主题，获取对应页面内容一并参考。

## 当前 wiki 页面内容
{context}

## 用户查询
{query}

请直接回答，引用 [[wikilink]] 来源。"""

    def __init__(self, store: WikiStore, llm: LLMFunc | None = None) -> None:
        self.store = store
        self._llm = llm

    # ── Ingest ──────────────────────────────────────────────

    def ingest(self, name: str, content: str) -> str:
        """两步 CoT 摄入: 保存原始文档 → 生成 wiki 页面"""
        # Step 0: 保存原始文档
        sha = self.store.add_source(name, content)
        self.store.append_log("INGEST_START", f"{name} ({sha})")

        # Step 1-2: LLM 分析 + 生成
        if self._llm:
            wiki_json = self._llm(
                system=self.INGEST_PROMPT,
                user=f"## 原始文档: {name}\n{content[:8000]}",
            )
            self._apply_ingest_result(wiki_json, name)
        else:
            # 无 LLM 时，简单创建源文档摘要
            self._simple_ingest(name, content, sha)

        self.store.append_log("INGEST_DONE", f"{name} ({sha})")
        return sha

    def _apply_ingest_result(self, result: str, source_name: str) -> None:
        """解析 LLM 返回的 JSON 并写入 wiki"""
        import json
        import re

        # 提取 JSON — 找 ```json...``` 或 ```...```
        match = re.search(r"```(?:json)?\s*(.+?)\s*```", result, re.DOTALL)
        json_str = match.group(1).strip() if match else None
        if not json_str:
            # 尝试找任何 { ... } 块
            brace_start = result.find("{")
            brace_end = result.rfind("}")
            if brace_start >= 0 and brace_end > brace_start:
                json_str = result[brace_start:brace_end + 1]

        if not json_str:
            self.store.append_log("INGEST_WARN", f"无法解析 LLM 输出: {source_name}")
            return

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            self.store.append_log("INGEST_WARN", f"JSON 解析失败: {source_name}")
            return

        pages: list[dict] = data.get("pages", [])
        for page in pages:
            subdir = page.get("subdir", "concepts")
            title = page.get("title", "untitled")
            content = self._build_page(subdir, title, page.get("content", ""), source_name)
            self.store.write_page(subdir, title, content)
            self.store.update_index_entry(title, subdir, subdir)

        # 更新 index 头部概览
        index_content = self.store.read_index()
        self.store.write_index(index_content)

    def _build_page(self, subdir: str, title: str, body: str, source_name: str) -> str:
        """组装带 frontmatter 的 wiki 页面"""
        return (
            "---\n"
            f'title: "{title}"\n'
            f"type: {subdir.rstrip('s')}\n"
            f"sources: [{source_name}]\n"
            f"created: {__import__('datetime').datetime.now().isoformat()[:10]}\n"
            "---\n\n"
            f"{body}\n"
        )

    def _simple_ingest(self, name: str, content: str, sha: str) -> None:
        """无 LLM 的回退：直接生成源文档摘要页"""
        title = f"source_{name}"
        body = f"```\n{content[:2000]}\n```\n\n**SHA:** {sha}"
        self.store.write_page("sources", title, self._build_page("sources", title, body, name))
        self.store.update_index_entry(title, "sources", "sources")

    # ── Query ───────────────────────────────────────────────

    def query(self, query: str, max_pages: int = 5) -> str:
        """查询 wiki，返回拼装后的上下文"""
        # Phase 1: 关键词匹配 wiki 页面标题 + 内容
        keywords = self._tokenize(query)
        candidates: list[tuple[str, Path]] = []
        for p in self.store.list_pages():
            text = p.read_text(encoding="utf-8")
            score = sum(1 for kw in keywords if kw in text.lower() or kw in p.stem.lower())
            if score > 0:
                candidates.append((p.stem, p))

        # Phase 2: 排序 + 截断
        candidates.sort(key=lambda x: x[0], reverse=True)
        top = candidates[:max_pages]

        # Phase 3: 按 wikilink 扩展
        seen = {stem for stem, _ in top}
        for stem, path in top[:]:
            text = path.read_text(encoding="utf-8")
            for link in self.store.extract_wikilinks(text):
                linked = self.store.find_page(link)
                if linked and linked.stem not in seen and len(top) < max_pages * 2:
                    seen.add(linked.stem)
                    top.append((linked.stem, linked))

        # Phase 4: 拼装 context
        parts = []
        for stem, path in top:
            text = path.read_text(encoding="utf-8")
            parts.append(f"--- {stem} ---\n{text[:1500]}")
        return "\n\n".join(parts) if parts else ""

    def _tokenize(self, text: str) -> list[str]:
        """简单分词（英文空格 + 中文二元组）"""
        text = text.lower()
        tokens = []
        # 英文单词
        for word in text.split():
            if word.isascii() and len(word) > 1:
                tokens.append(word)
        # 中文二元组
        for i in range(len(text) - 1):
            if "\u4e00" <= text[i] <= "\u9fff" and "\u4e00" <= text[i + 1] <= "\u9fff":
                tokens.append(text[i : i + 2])
        return list(set(tokens))

    # ── Lint ────────────────────────────────────────────────

    def lint(self) -> list[str]:
        """审查 wiki 状态"""
        issues: list[str] = []
        pages = self.store.list_pages()
        if not pages:
            issues.append("⚠️ Wiki 为空，没有页面")
            return issues

        # 检查孤立页面（无 wikilinks 指向它）
        all_content = " ".join(p.read_text() for p in pages)
        for p in pages:
            stem = p.stem
            if f"[[{stem}]]" not in all_content.replace(p.read_text(), ""):
                issues.append(f"🔗 孤立页面: [[{stem}]] 未被其他页面引用")

        # 检查破损 wikilink
        for p in pages:
            text = p.read_text()
            for link in self.store.extract_wikilinks(text):
                if not self.store.find_page(link):
                    issues.append(f"🔗 破损链接: [[{link}]] 在 {p.stem} 中")

        return issues
