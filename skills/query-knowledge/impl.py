"""query-knowledge 技能实现 — MCP 检索 + LLM 综合回答."""

import json
import time


def execute(context: dict) -> str:
    """MCP 检索 → LLM → template_card 回复。

    context 需包含:
        input_text: 用户问题
        user_id: 企业微信用户 ID
        send_md: 发送 markdown 的函数
        send_tpl: 发送 template_card 的函数
    """
    from knowledge_wiki.wiki.frontmatter import strip_frontmatter
    from knowledge_wiki.llm.ollama import call_json, call_short
    from knowledge_wiki.mcp.client import mcp_query

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    send_tpl = context.get("send_tpl")

    question = context.get("query") or context.get("input_text", "")
    question = question.strip()
    if question.startswith("?"):
        question = question[1:].strip()

    if not question:
        if send_md:
            send_md(user_id, "请输入查询内容，如：`? AI Workflow`")
        return ""

    if not user_id:
        return f"## 问答结果\n\n{question}\n\n*独立执行：需要 user_id 才能发送卡片.*"

    # 1. MCP 检索
    wiki_context = mcp_query(question)
    if not wiki_context:
        if send_md:
            send_md(user_id, "知识库查询失败，请重试。")
        return ""

    wiki_context = strip_frontmatter(wiki_context)

    # 2. LLM JSON 输出
    card_data = call_json(question, wiki_context)
    if not card_data or "cards" not in card_data:
        # Fallback: 关键字搜索
        from knowledge_wiki.wiki.search import keyword_search
        results = keyword_search(question)
        if not results:
            if send_md:
                send_md(user_id, f"知识库中暂无「{question}」相关内容。")
            return ""
        score, title, filepath = results[0]
        body = filepath.read_text()
        body_text = strip_frontmatter(body)
        # Extract helpers
        from knowledge_wiki.webhook.process import _extract_first_meaningful_text, _extract_kv_from_markdown, _extract_section_kv
        if send_tpl:
            send_tpl(user_id,
                title=title,
                summary=_extract_first_meaningful_text(body_text),
                details=_extract_kv_from_markdown(body_text) or _extract_section_kv(body_text),
                source_desc=title)
        return ""

    # 3. 发送卡片
    from knowledge_wiki.wiki.search import get_top_page_titles
    from knowledge_wiki.webhook.process import _normalize_details, _clean_markdown

    cards = card_data["cards"]
    top_page = get_top_page_titles(question)

    for i, card in enumerate(cards[:8]):
        if i > 0:
            time.sleep(0.8)
        details = _normalize_details(card.get("details", []))
        summary = card.get("summary", "")
        if not summary:
            summary = call_short(
                f"{card.get('title', question)} 的核心信息",
                json.dumps(details, ensure_ascii=False),
            )
        if send_tpl:
            send_tpl(user_id,
                title=card.get("title", question),
                summary=summary or "",
                details=details,
                source_desc=f"{top_page} ({i + 1}/{len(cards)})")

    # 4. 综合 markdown
    overall = card_data.get("summary", "")
    if overall and len(overall) > 100:
        clean = _clean_markdown(overall)
        if len(clean) > 50 and send_md:
            send_md(user_id, clean)

    return ""
