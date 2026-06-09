"""MCP ingest 工具 — 保存资料到 raw/ 并记录日志."""

from datetime import datetime
from pathlib import Path
from knowledge_wiki.config import settings
from knowledge_wiki.wiki.git import pull, push
from knowledge_wiki.wiki.paths import raw_dir


async def ingest_tool(source: str, domain: str = "收件箱") -> str:
    """将新资料保存到 raw/ 目录并记录日志."""
    pull()

    dest = raw_dir(domain)
    dest.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    is_url = source.startswith("http://") or source.startswith("https://")
    if is_url:
        filename = f"url-{ts}.md"
        content = f"# URL Ingest\n\n- 来源: {source}\n- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n待处理。"
    else:
        filename = f"note-{ts}.md"
        content = f"# Note Ingest\n\n- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{source}"

    filepath = dest / filename
    filepath.write_text(content)

    # 追加操作日志
    log_path = settings.wiki_root / "wiki" / "操作日志.md"
    log_entry = f"\n## [{datetime.now().strftime('%Y-%m-%d')}] ingest | {domain}\n"
    log_entry += f"- 来源: raw/{domain}/{filename}\n"
    log_entry += f"- 状态: 已保存，待处理\n"
    if log_path.exists():
        with log_path.open("a") as f:
            f.write(log_entry)

    git_result = push(f"ingest: {domain} - {filename}")

    return f"""资料已保存: `raw/{domain}/{filename}`

后续步骤:
1. 阅读 `AGENTS.md` 了解 ingest 流程
2. 阅读 `raw/{domain}/{filename}` 内容
3. 读取 `templates/source.md` 获取资料摘要模板
4. 创建 `wiki/资料摘要/` 页面
5. 更新 `wiki/Wiki 目录.md`
6. 提取概念、添加交叉引用

Git: {git_result}"""
