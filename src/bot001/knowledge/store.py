"""Wiki 文件系统操作 — index.md / log.md / wiki 页面管理"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot001.llm.client import LLMClient


class WikiStore:
    """管理 wiki 目录结构：sources/ + wiki/ + index.md + log.md"""

    def __init__(self, base_dir: str = "./data/wiki") -> None:
        self.base = Path(base_dir)
        self.sources_dir = self.base / "sources"
        self.wiki_dir = self.base / "wiki"
        self.index_file = self.base / "index.md"
        self.log_file = self.base / "log.md"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for d in (self.sources_dir, self.wiki_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ── Sources ──────────────────────────────────────────────

    def add_source(self, name: str, content: str) -> str:
        """保存原始文档到 sources/，返回 SHA256"""
        sha = hashlib.sha256(content.encode()).hexdigest()[:16]
        safe_name = re.sub(r"[^\w\-]", "_", name)
        path = self.sources_dir / f"{safe_name}_{sha}.md"
        path.write_text(content, encoding="utf-8")
        return sha

    def list_sources(self) -> list[Path]:
        return sorted(self.sources_dir.glob("*.md"))

    def get_source(self, sha: str) -> Path | None:
        for p in self.sources_dir.glob(f"*_{sha}.md"):
            return p
        return None

    # ── Wiki Pages ───────────────────────────────────────────

    def write_page(self, subdir: str, title: str, content: str) -> Path:
        """写入 wiki 页面，subdir 如 'concepts', 'entities', 'sources'"""
        safe = re.sub(r"[^\w\-]", "_", title)
        dir_path = self.wiki_dir / subdir
        dir_path.mkdir(parents=True, exist_ok=True)
        path = dir_path / f"{safe}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def read_page(self, subdir: str, title: str) -> str | None:
        safe = re.sub(r"[^\w\-]", "_", title)
        path = self.wiki_dir / subdir / f"{safe}.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def list_pages(self, subdir: str | None = None) -> list[Path]:
        root = self.wiki_dir / subdir if subdir else self.wiki_dir
        return sorted(root.rglob("*.md"))

    def find_page(self, title: str) -> Path | None:
        """按标题模糊查找 wiki 页面"""
        safe = re.sub(r"[^\w\-]", "_", title).lower()
        for p in self.wiki_dir.rglob("*.md"):
            if p.stem.lower() == safe:
                return p
        return None

    # ── Index ────────────────────────────────────────────────

    def read_index(self) -> str:
        if self.index_file.exists():
            return self.index_file.read_text(encoding="utf-8")
        return "# Wiki Index\n\n"

    def write_index(self, content: str) -> None:
        self.index_file.write_text(content, encoding="utf-8")

    def update_index_entry(self, title: str, page_type: str, subdir: str) -> None:
        """向 index.md 追加条目"""
        idx = self.read_index()
        link = f"[[{title}]]"
        entry = f"- [{page_type}] {link} — `wiki/{subdir}/`\n"
        if link not in idx:
            self.write_index(idx + entry)

    # ── Log ──────────────────────────────────────────────────

    def append_log(self, action: str, detail: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {action}: {detail}\n"
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(line)

    def read_log(self) -> str:
        if self.log_file.exists():
            return self.log_file.read_text(encoding="utf-8")
        return ""

    # ── Wikilinks ────────────────────────────────────────────

    def extract_wikilinks(self, content: str) -> list[str]:
        """提取 [[wikilink]] 中的标题"""
        return re.findall(r"\[\[([^\]]+)\]\]", content)

    def resolve_wikilink(self, title: str) -> str | None:
        """解析 wikilink 返回页面内容"""
        path = self.find_page(title)
        if path:
            return path.read_text(encoding="utf-8")
        return None
