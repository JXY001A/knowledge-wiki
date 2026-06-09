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


def stream_deepseek(model: str, messages: list[dict], max_tokens: int = 2048,
                     temperature: float = 0.3, timeout: int = 120):
    """DeepSeek 流式调用 — 逐 token 生成.

    Yields:
        每个 chunk 的 content 字符串
    """
    api_key = settings.deepseek_api_key
    if not api_key:
        _log.warning("DEEPSEEK_API_KEY not set, stream unavailable")
        yield ""
        return

    import urllib.request

    try:
        body = json.dumps({
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for line in resp:
                line = line.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]  # strip "data: " prefix
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        _log.warning("DeepSeek stream failed: %s", e)
        yield ""


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


def call_deepseek_query(question: str, context: str,
                         system_prompt: str = "",
                         model: str = "",
                         max_tokens: int = 2048,
                         temperature: float = 0.3) -> str | None:
    """调用 DeepSeek API 生成知识库问答（带引用）.

    Args:
        question: 用户问题
        context: 检索到的 wiki 上下文
        system_prompt: 自定义 system prompt（为空则使用默认查询 prompt）
        model: 模型名（默认使用 settings.deepseek_model_ingest）
        max_tokens: 最大 token 数
        temperature: 随机性参数

    Returns:
        回答文本或 None
    """
    api_key = settings.deepseek_api_key
    if not api_key:
        _log.warning("DEEPSEEK_API_KEY not set, skip DeepSeek query")
        return None

    if not system_prompt:
        system_prompt = (
            "你是个人知识库助手。基于提供的知识库资料回答用户问题。\n\n"
            "**要求**：\n"
            "1. 优先基于知识库资料回答，标注引用来源（用 [[页面名]] 格式）\n"
            "2. 回答结构清晰，用 ## 标题分段\n"
            "3. 用 **粗体** 强调关键术语\n"
            "4. 用 - 列表展示多项信息\n"
            "5. 不要用表格（|...|），不要用代码块（```）\n"
            "6. 只基于提供的资料，不要编造\n"
            "7. 回答末尾列出参考页面\n\n"
            "请用中文回答，200-500 字。"
        )

    if not model:
        model = settings.deepseek_model_ingest

    import urllib.request

    for attempt in range(3):
        try:
            body = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"## 知识库检索结果\n\n{context[:12000]}\n\n---\n\n## 用户问题\n\n{question}"},
                ],
                "stream": False,
                "temperature": temperature,
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
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                return result["choices"][0]["message"]["content"].strip()

        except Exception as e:
            if attempt < 2:
                delay = 2.0 ** attempt
                _log.warning("DeepSeek query failed (attempt %d/3): %s — retrying in %.1fs",
                             attempt + 1, e, delay)
                time.sleep(delay)
            else:
                _log.error("DeepSeek query failed after 3 attempts: %s", e)
                return None
