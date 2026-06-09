"""search-wiki 技能实现 — 关键词搜索 wiki."""


def execute(context: dict) -> str:
    """搜索 wiki 并返回匹配页面。

    context 需包含:
        input_text: 搜索关键词
        send_md: 发送 markdown 消息的函数（可选）
        user_id: 企业微信用户 ID（可选）
    """
    from knowledge_wiki.wiki.search import search_wiki

    text = context.get("input_text", "").strip()

    # 去除 ? 前缀和 搜索/查找 触发词
    for prefix in ["?", "搜索", "查找", "search", "find", "找一下"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break

    if not text:
        return "请输入搜索关键词，如：`? 搜索 MCP`"

    results = search_wiki(text, max_results=8)
    if not results:
        return f"未找到包含「{text}」的页面。"

    lines = [f"## 搜索结果：{text}（{len(results)} 条）\n"]
    for i, r in enumerate(results):
        lines.append(f"**{i + 1}. [[{r['title']}]]**")
        lines.append(f"路径: `{r['path']}`")
        lines.append(f"> {r['excerpt']}")
        lines.append("")

    return "\n".join(lines)
