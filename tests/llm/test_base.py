"""LLM 基础工具测试."""

import json
from knowledge_wiki.llm.base import extract_json, repair_json


def test_extract_json_clean():
    """提取干净 JSON."""
    text = '{"key": "value", "num": 42}'
    result = extract_json(text)
    assert result == text


def test_extract_json_with_markdown_block():
    """从 markdown 代码块中提取 JSON."""
    text = '```json\n{"key": "value"}\n```'
    result = extract_json(text)
    assert result == '{"key": "value"}'


def test_extract_json_with_prefix():
    """从前缀文本中提取 JSON."""
    text = '这是结果：\n{"name": "test"}\n\n更多文本'
    result = extract_json(text)
    assert result == '{"name": "test"}'


def test_extract_json_nested():
    """提取嵌套 JSON."""
    text = '{"outer": {"inner": [1, 2, 3]}}'
    result = extract_json(text)
    assert result == text


def test_extract_json_no_braces():
    """无花括号返回 None."""
    assert extract_json("plain text") is None
    assert extract_json("[1, 2, 3]") is None


def test_repair_json_trailing_comma():
    """修复尾逗号."""
    broken = '{"a": 1, "b": 2,}'
    result = repair_json(broken)
    assert result == {"a": 1, "b": 2}


def test_repair_json_unquoted_keys():
    """修复未引号 key."""
    broken = '{name: "test", age: 30}'
    result = repair_json(broken)
    assert result == {"name": "test", "age": 30}


def test_repair_json_valid():
    """有效 JSON 直接解析."""
    valid = '{"key": "value"}'
    result = repair_json(valid)
    assert result == {"key": "value"}


def test_repair_json_invalid():
    """无法修复的 JSON 返回 None."""
    assert repair_json("not json at all{") is None
