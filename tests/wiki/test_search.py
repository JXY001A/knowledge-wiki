"""搜索功能测试."""

from knowledge_wiki.wiki.search import extract_wikilinks


def test_extract_wikilinks_simple():
    """提取简单 [[wikilinks]]."""
    text = "参见 [[MCP（Model Context Protocol）]] 和 [[ReAct架构]]。"
    links = extract_wikilinks(text)
    assert "MCP（Model Context Protocol）" in links
    assert "ReAct架构" in links


def test_extract_wikilinks_with_alias():
    """提取带别名的 wikilinks."""
    text = "参考 [[Agent Skill|Agent技能]] 文档。"
    links = extract_wikilinks(text)
    assert "Agent Skill" in links


def test_extract_wikilinks_empty():
    """空文本返回空列表."""
    assert extract_wikilinks("") == []
    assert extract_wikilinks("普通文本无链接") == []


def test_extract_wikilinks_multiple():
    """提取多个 wikilinks."""
    text = "[[A]] [[B]] [[C]] 之间的关系。"
    links = extract_wikilinks(text)
    assert len(links) == 3
    assert links == ["A", "B", "C"]
