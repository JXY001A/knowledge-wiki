"""query-knowledge 技能实现 — 双路检索 + 多模型路由 + 知识缺口检测.

v4: 语义检索补充 BM25，分数阈值判断，DeepSeek 复杂问题路由，
    带引用回答，知识缺口自动记录。
"""

# BM25 分数阈值：低于此值视为"知识库无相关覆盖"
RELEVANCE_THRESHOLD = 0.3

# 上下文长度阈值：超过此值路由到 DeepSeek（复杂问题）
COMPLEX_CONTEXT_THRESHOLD = 1500


def execute(context: dict) -> str:
    """执行知识查询 — 检索 → 阈值判断 → LLM 回答 → 缺口记录.

    context 需包含:
        input_text: 用户问题
        user_id: 用户 ID
        send_md: 发送 markdown 的函数
        history: 对话历史（可选）
    """
    import logging
    _log = logging.getLogger(__name__)

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

    # 0. 注入记忆上下文
    try:
        from knowledge_wiki.memory.working import build_system_prompt_suffix
        memory_context = build_system_prompt_suffix(user_id if user_id else None)
    except Exception:
        memory_context = ""

    # 0.5 注入对话历史
    history = context.get("history", [])
    history_text = ""
    if history:
        parts = []
        for m in history[-10:]:
            role = "用户" if m.get("role") == "user" else "助手"
            content = m.get("content", "")[:300]
            parts.append(f"{role}：{content}")
        history_text = "## 对话历史\n" + "\n".join(parts) + "\n\n"

    # 1. 双路检索（BM25 + Embedding → RRF 融合）
    try:
        from knowledge_wiki.wiki.retrieval.pipeline import run_pipeline_detailed
        result = run_pipeline_detailed(question)
        wiki_context = result["text"]
        top_score = result.get("bm25_top_score", 0)
        top_title = result.get("top_title", "")
        has_relevant = result.get("has_relevant", bool(wiki_context and "未找到" not in wiki_context))
        result_count = result.get("result_count", 0)
        _log.info("检索结果: top=%s score=%.3f relevant=%s count=%d",
                   top_title, top_score, has_relevant, result_count)
    except Exception as e:
        _log.warning("检索失败: %s", e)
        if send_md:
            send_md(user_id, "知识库查询失败，请重试。")
        return ""

    # 2. 知识缺口判断
    is_gap = not has_relevant and top_score < RELEVANCE_THRESHOLD

    # 3. 选择回答模型和策略
    if is_gap:
        answer = _generate_gap_answer(question, wiki_context, history_text, memory_context, user_id)
    else:
        answer = _generate_wiki_answer(question, wiki_context, history_text, memory_context)

    # 4. 如果所有回答都失败，用原始 wiki 内容兜底
    if not answer:
        answer = wiki_context[:2800]

    # 5. 发送回答
    if send_md:
        send_md(user_id, answer[:3000])

    # 6. 异步评估 + 缺口记录
    try:
        import threading
        def _eval():
            from knowledge_wiki.eval.scorer import evaluate_and_record
            evaluate_and_record(question[:200], answer[:2000], wiki_context[:3000], user_id)
            # 知识缺口记录
            if is_gap:
                _record_gap(question, top_score, user_id)
        threading.Thread(target=_eval, daemon=True).start()
    except Exception:
        pass

    return ""


def _generate_wiki_answer(question: str, wiki_context: str,
                           history_text: str, memory_context: str) -> str | None:
    """基于 wiki 资料生成带引用的回答。

    使用多级路由：
    - 上下文 < 1500 字符 → 本地 Ollama（qwen2.5:3b，快速）
    - 上下文 ≥ 1500 字符 → DeepSeek（质量更高，支持引用标注）
    """
    full_context = history_text + wiki_context
    if memory_context:
        full_context = memory_context + "\n---\n" + full_context
    max_ctx = min(len(full_context), 12000)

    if len(wiki_context) < COMPLEX_CONTEXT_THRESHOLD:
        # 简单问题：本地 Ollama
        from knowledge_wiki.llm.ollama import call_detailed
        return call_detailed(question, full_context[:max_ctx])

    # 复杂问题：DeepSeek 高质量回答
    from knowledge_wiki.llm.deepseek import call_deepseek_query
    return call_deepseek_query(question, full_context[:max_ctx])


def _generate_gap_answer(question: str, wiki_context: str,
                          history_text: str, memory_context: str,
                          user_id: str) -> str | None:
    """知识库无覆盖时的兜底回答。

    策略：
    1. 尝试用 DeepSeek 通用知识回答
    2. 标注"以下为模型通用知识，非知识库内容"
    3. 记录知识缺口
    """
    gap_warning = "⚠️ **知识库暂无直接覆盖此主题的资料**\n\n"

    try:
        from knowledge_wiki.llm.deepseek import call_deepseek_query
        general = call_deepseek_query(
            question,
            f"用户问题：{question}\n\n请用你的通用知识回答。标注：以下内容来自模型通用知识，非知识库资料。",
            system_prompt=DEEPSEEK_GENERAL_PROMPT,
        )
        if general:
            return gap_warning + general
    except Exception:
        pass

    # DeepSeek 不可用时用 Ollama 兜底
    try:
        from knowledge_wiki.llm.ollama import call_detailed
        general = call_detailed(question, memory_context or question)
        if general:
            return gap_warning + "> 以下为模型通用知识，非知识库特定资料\n\n" + general
    except Exception:
        pass

    return gap_warning + "_暂时无法生成回答，请稍后重试或提供更多上下文。_"


def _record_gap(question: str, score: float, user_id: str) -> None:
    """记录知识缺口到 memory_events，供 auto_ingest 使用。

    同一缺口多次出现后会触发自动摄取。
    """
    try:
        from knowledge_wiki.memory.db import get_db, init_schema
        from datetime import datetime, timezone

        conn = get_db()
        init_schema(conn)

        # 提取关键词（取问题前 60 字作为缺口描述）
        gap_topic = question[:60].strip()

        conn.execute(
            """INSERT INTO memory_events (event_type, summary, details, score, user_id, source, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                "gap",
                f"知识缺口：{gap_topic}",
                f"查询：{question}\nBM25 分数：{score:.3f}\n状态：知识库无相关覆盖",
                0,  # score=0 表示缺口（非正常评估）
                user_id,
                "auto",
                "知识缺口, 待摄取",
                datetime.now(timezone.utc).isoformat(),
            ],
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


DEEPSEEK_GENERAL_PROMPT = """你是个人知识库助手。用户的问题在当前知识库中没有直接覆盖的资料。

请用你的通用知识回答用户问题：
1. 在回答开头注明"以下内容为通用知识，建议后续补充相关资料到知识库"
2. 如实回答，不确定的地方明确说明
3. 回答末尾建议用户可以提供哪些资料来补充知识库

请用中文回答，300-500 字。"""
