"""frontmatter 解析 / 剥离测试."""

import os

from knowledge_wiki.wiki.frontmatter import parse_frontmatter, strip_frontmatter


def test_parse_frontmatter(sample_page_file):
    """解析有效 frontmatter."""
    fm = parse_frontmatter(sample_page_file)
    assert fm is not None
    assert fm["title"] == "测试页面"
    assert fm["type"] == "concept"
    assert fm["tags"] == ["概念", "测试"]
    assert fm["confidence"] == "high"


def test_parse_nonexistent():
    """不存在文件返回 None."""
    from pathlib import Path
    fm = parse_frontmatter(Path("/nonexistent/file.md"))
    assert fm is None


def test_strip_frontmatter(sample_frontmatter_md):
    """剥离 frontmatter 后返回正文."""
    body = strip_frontmatter(sample_frontmatter_md)
    assert "---" not in body[:10]
    assert "测试概念的定义" in body
    assert "## 是什么" in body


def test_strip_frontmatter_no_fm():
    """无 frontmatter 的文本原样返回."""
    text = "# 普通标题\n\n正文内容。"
    result = strip_frontmatter(text)
    assert result == text
