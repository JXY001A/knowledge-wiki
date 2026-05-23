"""技能注册表测试."""

from knowledge_wiki.skill.registry import list_skills, find_skill, get_skills_summary


def test_list_skills():
    """注册表应返回 5 个技能."""
    skills = list_skills()
    assert len(skills) >= 5
    names = {s.name for s in skills}
    assert "search-wiki" in names
    assert "query-knowledge" in names
    assert "ingest-article" in names
    assert "lint-wiki" in names
    assert "save-note" in names


def test_find_skill_exists():
    """按名称查找存在的技能."""
    skill = find_skill("search-wiki")
    assert skill is not None
    assert skill.name == "search-wiki"
    assert skill.tier == 1
    assert skill.model == "local"


def test_find_skill_not_exists():
    """查找不存在的技能返回 None."""
    assert find_skill("nonexistent-skill") is None


def test_get_skills_summary():
    """摘要应包含所有技能名称."""
    summary = get_skills_summary()
    assert "search-wiki" in summary
    assert "query-knowledge" in summary
    assert "ingest-article" in summary
    assert "Tier 1" in summary
    assert "Tier 2" in summary


def test_skill_has_required_fields():
    """每个技能应有 name, version, description, tier, model."""
    for skill in list_skills():
        assert skill.name
        assert skill.version
        assert skill.description
        assert skill.tier in (1, 2, 3)
        assert skill.model in ("local", "deepseek", "auto")


def test_ingest_article_uses_deepseek():
    """ingest-article 应配置为 deepseek 模型."""
    skill = find_skill("ingest-article")
    assert skill is not None
    assert skill.model == "deepseek"
