"""路径工具 — wiki 和 raw 目录的路径解析."""

from datetime import datetime
from pathlib import Path
from knowledge_wiki.config import settings
from knowledge_wiki.wiki.atomic import atomic_write

WIKI_ROOT = settings.wiki_root
RAW_INBOX = WIKI_ROOT / "raw" / "收件箱"


def wiki_dir() -> Path:
    """返回 wiki/ 目录路径."""
    return WIKI_ROOT / "wiki"


def raw_dir(domain: str = "") -> Path:
    """返回 raw/ 目录或 raw/<domain>/ 子目录路径."""
    d = WIKI_ROOT / "raw"
    if domain:
        d = d / domain
    return d


def save_to_inbox(content: str, msg_type: str = "text") -> Path:
    """将内容保存到 raw/收件箱/，返回文件路径."""
    RAW_INBOX.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filepath = RAW_INBOX / f"wecom-{msg_type}-{ts}.md"
    text = f"# 企业微信消息\n\n- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n- 类型: {msg_type}\n\n{content}"
    atomic_write(filepath, text)
    return filepath


def find_page_path(title: str) -> str | None:
    """在 wiki/ 中按标题查找页面文件路径."""
    wd = wiki_dir()
    for md in sorted(wd.rglob("*.md")):
        text = md.read_text()
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                for line in text[3:end].splitlines():
                    if line.startswith("title:") and title in line:
                        return str(md.relative_to(WIKI_ROOT))
        if title in md.stem:
            return str(md.relative_to(WIKI_ROOT))
    return None
