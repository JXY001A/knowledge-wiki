"""MCP search 工具 — 关键词搜索 wiki."""

from knowledge_wiki.wiki.search import search_wiki


async def search_tool(keyword: str) -> str:
    """按关键词在 wiki 中搜索，返回匹配页面和摘录."""
    results = search_wiki(keyword)
    if not results:
        return f"未找到包含「{keyword}」的页面。"

    lines = [f"## 搜索结果：{keyword}（{len(results)} 个页面）\n"]
    for r in results:
        lines.append(f"### [[{r['title']}]]")
        lines.append(f"路径: `{r['path']}`")
        lines.append(f"```\n{r['excerpt']}\n```\n")
    return "\n".join(lines)
