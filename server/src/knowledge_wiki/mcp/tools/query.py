"""MCP query 工具 — 基于 wiki 回答问题.

v2: 检索升级为 catalog → BM25 → layered 四阶段流水线。
旧实现保留在 _query_tool_legacy()，通过 settings.use_new_retrieval 控制切换。
"""

from knowledge_wiki.config import settings
from knowledge_wiki.wiki.git import pull
from knowledge_wiki.wiki.search import list_wiki_pages


async def query_tool(question: str) -> str:
    """基于 wiki 知识库回答问题（新检索流水线或旧实现）。"""
    pull_result = pull()

    if settings.use_new_retrieval:
        return await _query_tool_new(question, pull_result)
    else:
        return await _query_tool_legacy(question, pull_result)


async def _query_tool_legacy(question: str, pull_result: str) -> str:
    """旧实现：关键词 in 全量扫描（保留用于回滚）。"""
    pages = list_wiki_pages()
    keywords = question.lower().split()

    # 按标题和标签相关性排序
    relevant = []
    for p in pages:
        text = f"{p['title']} {' '.join(p.get('tags', []))}"
        score = sum(1 for kw in keywords if kw in text.lower())
        if score > 0:
            relevant.append((score, p))

    relevant.sort(key=lambda x: x[0], reverse=True)

    if not relevant:
        return (
            f"未在 wiki 中找到与「{question}」相关的页面。\n\n"
            f"建议：\n"
            f"- 尝试不同的关键词\n"
            f"- 使用 `search` 工具进行关键词匹配\n"
            f"- 使用 `ingest` 工具添加相关资料"
        )

    lines = [f"## 查询：{question}\n"]
    lines.append(f"找到 {len(relevant)} 个相关页面：\n")

    for score, p in relevant[:8]:
        filepath = settings.wiki_root / p["path"]
        content = filepath.read_text() if filepath.exists() else ""
        preview = content[:800] if len(content) > 800 else content
        lines.append(f"### [[{p['title']}]]")
        lines.append(f"类型: {p['type']} | 标签: {', '.join(p['tags'])} | 更新: {p['updated']}")
        lines.append(f"\n{preview}\n")
        lines.append("---\n")

    lines.append(f"\n同步状态: {pull_result}")
    return "\n".join(lines)


async def _query_tool_new(question: str, pull_result: str) -> str:
    """新实现：catalog → BM25 → layered 四阶段检索流水线。"""
    from knowledge_wiki.wiki.retrieval.pipeline import run_pipeline

    try:
        result = run_pipeline(question)
        return result + f"\n\n同步状态: {pull_result}"
    except Exception:
        # 新流水线失败时自动回退到旧实现
        import logging
        logging.getLogger(__name__).warning(
            "检索流水线失败，回退旧实现", exc_info=True
        )
        return await _query_tool_legacy(question, pull_result)
