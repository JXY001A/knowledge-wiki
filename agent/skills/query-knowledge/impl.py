"""query-knowledge 技能实现 — 新检索流水线 + LLM markdown 回答."""


def execute(context: dict) -> str:
    """新检索流水线 → LLM markdown → 回复。

    v3: 绕开 MCP，直接调用检索流水线（避免 MCP 协议开销和不一致）。

    context 需包含:
        input_text: 用户问题
        user_id: 企业微信用户 ID
        send_md: 发送 markdown 的函数
    """
    from knowledge_wiki.llm.ollama import call_detailed
    from knowledge_wiki.wiki.retrieval.pipeline import run_pipeline

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

    # 0. 注入工作记忆上下文（最近操作记录）
    try:
        from knowledge_wiki.memory.working import build_system_prompt_suffix
        memory_context = build_system_prompt_suffix(user_id if user_id else None)
    except Exception:
        memory_context = ""

    # 0.5 注入对话历史（多轮对话上下文）
    history = context.get("history", [])
    history_text = ""
    if history:
        parts = []
        for m in history[-10:]:  # 最近 10 轮
            role = "用户" if m.get("role") == "user" else "助手"
            content = m.get("content", "")[:300]
            parts.append(f"{role}：{content}")
        history_text = "## 对话历史\n" + "\n".join(parts) + "\n\n"

    # 1. 新检索流水线（catalog → BM25 → layered）——直接调用，不经过 MCP
    try:
        wiki_context = run_pipeline(question)
    except Exception:
        if send_md:
            send_md(user_id, "知识库查询失败，请重试。")
        return ""

    if not wiki_context:
        if send_md:
            send_md(user_id, "知识库查询失败，请重试。")
        return ""

    # 2. LLM 格式化回答（注入对话历史 + 记忆上下文）
    # 检索管线三层组装预算 8000 token ≈ 16000 字符
    # 按 LLM 上下文窗口动态分配，而非硬截断
    full_context = history_text + wiki_context
    if memory_context:
        full_context = memory_context + "\n---\n" + full_context
    max_ctx = min(len(full_context), 12000)  # qwen2.5:3b 支持 32K，留 20K 给回答
    answer = call_detailed(question, full_context[:max_ctx])
    if not answer:
        answer = wiki_context[:2800]

    # 3. 发送 markdown 回答
    if send_md:
        send_md(user_id, answer[:3000])

    # 4. 异步评估回答质量（不阻塞回复）
    try:
        import threading
        def _eval():
            from knowledge_wiki.eval.scorer import evaluate_and_record
            evaluate_and_record(question[:200], answer[:2000], wiki_context[:3000], user_id)
        threading.Thread(target=_eval, daemon=True).start()
    except Exception:
        pass

    return ""
