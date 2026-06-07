"""技能引擎测试 — 意图匹配."""

from knowledge_wiki.skill.engine import match_skill, generate_tier1_context


def test_match_query_intent():
    """查询类意图匹配 query-knowledge."""
    queries = ["AI Workflow 是什么", "介绍一下 MCP", "怎么使用 DeepSeek", "对比 RAG 和 Agent"]
    for q in queries:
        skill = match_skill(q)
        assert skill is not None, f"Failed to match: {q}"
        assert skill.name == "query-knowledge", f"Expected query-knowledge for '{q}', got {skill.name}"


def test_match_search_intent():
    """搜索类意图匹配 search-wiki."""
    queries = ["搜索 MCP 协议", "帮我查找 transformer", "找一下 RAG 相关"]
    for q in queries:
        skill = match_skill(q)
        assert skill is not None, f"Failed to match: {q}"
        assert skill.name == "search-wiki", f"Expected search-wiki for '{q}', got {skill.name}"


def test_match_lint_intent():
    """巡检类意图匹配 lint-wiki."""
    queries = ["检查 wiki 健康", "lint wiki", "知识库巡检"]
    for q in queries:
        skill = match_skill(q)
        assert skill is not None, f"Failed to match: {q}"
        assert skill.name == "lint-wiki", f"Expected lint-wiki for '{q}', got {skill.name}"


def test_match_save_intent():
    """保存类意图匹配 save-note（不含"笔记"——已迁移到 note-quick）."""
    queries = ["保存一段文字", "记录今天的工作", "存一下这个"]
    for q in queries:
        skill = match_skill(q)
        assert skill is not None, f"Failed to match: {q}"
        assert skill.name == "save-note", f"Expected save-note for '{q}', got {skill.name}"


def test_no_match_for_url():
    """URL 不应匹配任何技能（由 process_message 直接路由）."""
    skill = match_skill("https://example.com/article")
    # URL 不应包含中文触发词，因此匹配为 None
    assert skill is None


def test_generate_tier1_context():
    """Tier 1 上下文应包含核心技能."""
    ctx = generate_tier1_context()
    assert "search-wiki" in ctx
    assert "query-knowledge" in ctx
    assert "ingest-article" in ctx
    assert "save-note" in ctx
    # Tier 2 不应在 Tier 1 上下文中
    assert "lint-wiki" not in ctx
