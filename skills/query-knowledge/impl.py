"""query-knowledge 技能实现 — 新检索流水线 + LLM markdown 回答."""


def execute(context: dict) -> str:
    """新检索流水线 → LLM markdown → 回复。

    v2: 使用 call_detailed（markdown 格式）替代 call_json（JSON cards），
    新检索流水线输出的结构化 markdown 对小模型更友好。

    context 需包含:
        input_text: 用户问题
        user_id: 企业微信用户 ID
        send_md: 发送 markdown 的函数
        send_tpl: 发送 template_card 的函数
    """
    from knowledge_wiki.wiki.frontmatter import strip_frontmatter
    from knowledge_wiki.llm.ollama import call_detailed
    from knowledge_wiki.mcp.client import mcp_query

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")

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

    # 1. 新检索流水线（catalog → BM25 → layered）
    wiki_context = mcp_query(question)
    if not wiki_context:
        if send_md:
            send_md(user_id, "知识库查询失败，请重试。")
        return ""

    wiki_context = strip_frontmatter(wiki_context)

    # 2. qwen2.5:3b markdown 格式化（失败时直接用检索原文）
    answer = call_detailed(question, wiki_context)
    if not answer:
        answer = wiki_context[:3000]

    # 3. 发送 markdown 回答
    if send_md:
        send_md(user_id, answer[:3000])

    return ""
