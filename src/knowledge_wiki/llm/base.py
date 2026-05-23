"""LLM 通用基类 — httpx 共享客户端、JSON 修复容错."""

import json
import re


def extract_json(text: str) -> str | None:
    """从 LLM 响应中提取 JSON —— 去除 markdown 代码块标记后做括号匹配."""
    clean = text.strip()
    clean = re.sub(r"```(?:json)?\s*", "", clean)
    clean = re.sub(r"```", "", clean)
    clean = clean.strip()

    start = clean.find("{")
    if start == -1:
        return None

    depth = 0
    for i, ch in enumerate(clean[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return clean[start:i + 1]

    return None


def repair_json(json_str: str) -> dict | None:
    """尝试解析 JSON，失败时修复常见错误后重试."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 尾逗号
    fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
    # 未引号的 key
    fixed = re.sub(r"([{,])\s*([a-zA-Z_]+)\s*:", r'\1"\2":', fixed)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None
