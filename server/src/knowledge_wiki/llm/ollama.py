"""Ollama API 客户端 — 本地模型调用（qwen2.5:3b, llama3.2:1b）."""

import json
from knowledge_wiki.config import settings
from knowledge_wiki.llm.base import extract_json, repair_json

OLLAMA_CHAT_URL = f"{settings.ollama_base_url}/api/chat"


def _call_ollama(model: str, messages: list[dict], num_predict: int = 600,
                 temperature: float = 0.1, timeout: int = 60) -> str | None:
    """通用 Ollama chat API 调用."""
    import urllib.request

    try:
        body = json.dumps({
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": num_predict, "temperature": temperature},
        }).encode()

        req = urllib.request.Request(
            OLLAMA_CHAT_URL,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = json.loads(resp.read()).get("message", {}).get("content", "").strip()
            return content if content else None
    except Exception:
        return None


def call_json(question: str, context: str) -> dict | None:
    """调用 qwen2.5:3b 生成结构化 JSON 用于 template_card."""
    import re

    system = (
        "Output ONLY valid JSON. No other text.\n"
        "Format: {\"summary\":\"整体概述\",\"cards\":[{\"title\":\"分类\",\"summary\":\"100-200字摘要\","
        "\"details\":[[\"键名\",\"值\"],[\"键名2\",\"值2\"]]}]}\n"
        "CRITICAL: details must be an array of 2-element arrays: [[\"k\",\"v\"],[\"k\",\"v\"]].\n"
        "NEVER use objects like {\"键\":\"k\",\"值\":\"v\"} in details.\n"
        "Rules:\n"
        "- summary: one-sentence overall answer (Chinese, 50-100 chars).\n"
        "- cards: split into 2-5 logical categories.\n"
        "- Each card: 3-8 detail pairs. Use real data only.\n"
        "- Always respond in Chinese."
    )

    raw = _call_ollama(
        model="qwen2.5:3b",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"[Wiki]\n{context}\n\n[Q]\n{question}"},
        ],
        num_predict=2000,
        temperature=0.1,
        timeout=60,
    )

    if not raw:
        return None

    # Save debug output
    try:
        with open("/tmp/llm_debug.txt", "w") as f:
            f.write(raw)
    except Exception:
        pass

    clean = raw.strip()
    clean = re.sub(r"```(?:json)?\s*", "", clean)
    clean = re.sub(r"```", "", clean)
    clean = clean.strip()

    json_str = extract_json(clean)
    if not json_str:
        print(f"[llm] Ollama JSON: no JSON in {clean[:150]}", flush=True)
        return None

    parsed = repair_json(json_str)
    if parsed:
        print(f"[llm] Ollama JSON OK, keys={list(parsed.keys())}", flush=True)
    else:
        print("[llm] Ollama JSON parse failed", flush=True)
    return parsed


def call_short(question: str, context: str) -> str | None:
    """调用 qwen2.5:3b 生成一句话摘要."""
    return _call_ollama(
        model="qwen2.5:3b",
        messages=[
            {"role": "system", "content": "Answer in ONE short Chinese sentence based on the wiki content. No formatting."},
            {"role": "user", "content": f"Wiki:\n{context[:2000]}\n\nQ: {question}"},
        ],
        num_predict=120,
        temperature=0.1,
        timeout=30,
    )


def call_detailed(question: str, context: str, num_predict: int = 1500) -> str | None:
    """调用 qwen2.5:3b 生成详细 markdown 回答."""
    return _call_ollama(
        model="qwen2.5:3b",
        messages=[
            {"role": "system", "content": (
                "用中文回答，详细但不过于啰嗦\n"
                "用 ## 标题分段\n"
                "用 **粗体** 强调关键术语\n"
                "用 `代码` 标记技术名词\n"
                "用 - 列表展示多项信息\n"
                "不要用表格（|...|），不要用代码块（```）\n"
                "只基于提供的资料，不要编造\n"
                "200-400字"
            )},
            {"role": "user", "content": f"[Wiki]\n{context}\n\n[Q]\n{question}"},
        ],
        num_predict=num_predict,
        temperature=0.3,
        timeout=120,
    )


def call_fallback(question: str, context: str) -> str | None:
    """调用 llama3.2:1b 作为最终回退."""
    return _call_ollama(
        model="llama3.2:1b",
        messages=[
            {"role": "system", "content": "Answer based on the wiki content. Be concise. Chinese."},
            {"role": "user", "content": f"Wiki:\n{context[:1500]}\n\nQ: {question}"},
        ],
        num_predict=200,
        temperature=0.1,
        timeout=30,
    )
