"""DeepSeek API 客户端 — ingest 内容分析."""

import json
import re
import time
import logging
from knowledge_wiki.config import settings
from knowledge_wiki.llm.base import extract_json

_log = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = settings.deepseek_model_ingest

INGEST_SYSTEM_PROMPT = (
    "你是知识库管理助手。阅读网页内容，输出结构化 JSON 用于生成 wiki 页面。\n\n"
    "## 输出格式\n\n"
    "严格输出以下 JSON 结构，不要 markdown 代码块：\n"
    '{"title":"资料摘要：<10字主题>","domain":"<领域>","tags":["标签1","标签2","标签3"],'
    '"summary":"<100-150字摘要>","key_points":["要点1","要点2","要点3","要点4"],'
    '"notes":"<详细笔记，整理原文关键内容，800-1500字，markdown格式>",'
    '"quotes":"<原文中值得引用的关键数据、观点或结论>",'
    '"concepts":[{"name":"概念名","definition":"一句话定义（≤50字）","importance":"为什么重要"}],'
    '"related_pages":["[[已存在的相关页面]]"]}\n\n'
    "## 规则\n\n"
    "1. title: 必须以\"资料摘要：\"开头，后接10字以内的核心主题\n"
    "2. domain: 从 [AI平台, AI应用, MCP, 知识工程, 工具, 部署运维, 产品设计, 商业, LLM, Agent, 基础设施, 其他] 选最匹配的1个\n"
    "3. tags: 3-5个，优先从 [概念, 教程, 深度, 综述, 观点, 资讯, 工具, 范式, 反模式, 案例, 基准, 最佳实践, 智能体, AI编程, 提示工程, 基础设施, 生态, 研究, 前端, 后端, 架构, 运维, 安全] 中选择\n"
    "4. 所有内容使用中文\n"
    "5. 严格基于原文，不编造信息\n"
    "6. summary: 100-150字的完整摘要，概括文章核心内容\n"
    "7. key_points: 4-6个核心要点，每个20-40字\n"
    "8. notes: 用 markdown 详细整理原文关键内容，800-1500字，保留重要细节、数据和观点\n"
    "9. concepts: 提取2-5个核心概念，每个含 name（概念名）、definition（≤50字定义）、importance（为什么重要）\n"
    "10. quotes: 摘录原文值得引用的关键数据或观点（原文摘录，中文）\n"
    "11. related_pages: 推测可能与本文相关的 wiki 已有页面（使用 [[wikilink]] 格式），如不确定填空数组"
)


def call_ingest(content: str, url: str = "") -> dict | None:
    """调用 DeepSeek API 分析内容，返回结构化 wiki 数据（带重试）."""
    api_key = settings.deepseek_api_key
    if not api_key:
        _log.warning("DEEPSEEK_API_KEY not set")
        return None

    import urllib.request

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            body = json.dumps({
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": INGEST_SYSTEM_PROMPT},
                    {"role": "user", "content": content[:40000]},
                ],
                "stream": False,
                "temperature": 0.1,
                "max_tokens": 4096,
            }).encode()

            req = urllib.request.Request(
                DEEPSEEK_API_URL,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                raw_content = result["choices"][0]["message"]["content"]
            break  # success
        except Exception as e:
            if attempt < max_retries:
                delay = 2.0 ** attempt
                _log.warning("DeepSeek call failed (attempt %d/%d): %s — retrying in %.1fs",
                             attempt + 1, max_retries + 1, e, delay)
                time.sleep(delay)
            else:
                _log.error("DeepSeek call failed after %d attempts: %s", max_retries + 1, e)
                return None

    if not raw_content or not raw_content.strip():
        _log.warning("DeepSeek ingest: empty response")
        return None

    # Save debug output
    try:
        with open("/tmp/llm_debug.txt", "w") as f:
            f.write(raw_content)
    except Exception:
        pass

    json_str = extract_json(raw_content)
    if not json_str:
        _log.warning("DeepSeek ingest: no JSON in %s", raw_content[:200])
        return None

    parsed = json.loads(json_str)
    _log.info("DeepSeek ingest OK: %s", parsed.get("title", "?"))
    return parsed


def call_summarize(content: str, max_tokens: int = 1024) -> str | None:
    """调用 DeepSeek API 生成简短摘要."""
    api_key = settings.deepseek_api_key
    if not api_key:
        return None

    import urllib.request

    try:
        body = json.dumps({
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "用一段中文总结以下内容的核心要点（200字以内）。"},
                {"role": "user", "content": content[:8000]},
            ],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }).encode()

        req = urllib.request.Request(
            DEEPSEEK_API_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"[llm] DeepSeek summarize failed: {e}", flush=True)
        return None
