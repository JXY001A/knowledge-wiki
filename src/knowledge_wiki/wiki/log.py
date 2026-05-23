"""操作日志 — 追加 ingest / query / lint 记录."""

from datetime import datetime
from knowledge_wiki.config import settings
from knowledge_wiki.wiki.builder import extract_concept_names


def append_ingest_log(data: dict, url: str, page_title: str):
    """追加 ingest 条目到 wiki/操作日志.md."""
    log_path = settings.wiki_root / "wiki" / "操作日志.md"
    if not log_path.exists():
        return

    today = datetime.now().strftime("%Y-%m-%d")
    concept_names = extract_concept_names(data.get("concepts", []))
    domain = data.get("domain", "未知")
    summary = data.get("summary", "")

    entry = f"""
## [{today}] ingest | {page_title}

- 来源：{url}
- 新建页面：[[{page_title}]]
- 新增概念：{", ".join(f"[[{c}]]" for c in concept_names) if concept_names else "无"}
- 领域：{domain}
- 核心洞察：{summary}
"""
    _insert_entry(log_path, entry)


def append_query_log(question: str, pages: list[str], result: str):
    """追加 query 条目到操作日志."""
    log_path = settings.wiki_root / "wiki" / "操作日志.md"
    if not log_path.exists():
        return

    today = datetime.now().strftime("%Y-%m-%d")
    pages_str = "、".join(f"[[{p}]]" for p in pages[:5]) if pages else "无"
    entry = f"""
## [{today}] query | {question[:50]}

- 查阅页面：{pages_str}
- 结果：{result}
"""
    _insert_entry(log_path, entry)


def _insert_entry(log_path, entry: str):
    """将条目插入操作日志顶部（在提示文本之后）."""
    content = log_path.read_text()
    marker = "> 每次 ingest / query / lint"
    pos = content.find(marker)
    if pos != -1:
        insert_at = content.find("\n", pos) + 1
        if content[insert_at] == "\n":
            insert_at += 1
    else:
        insert_at = len(content)
    updated = content[:insert_at] + entry + "\n" + content[insert_at:]
    log_path.write_text(updated)
