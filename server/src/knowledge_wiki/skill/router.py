# ============================================================================
# LLM Tool Router — DeepSeek function-calling 自动路由
# ============================================================================
# 替代 skill/engine.py 中的 match_skill() 关键词匹配。
#
# 工作流程：
#   1. 用户消息 → 构建 messages（system + 历史 + 用户消息）
#   2. 发送给 DeepSeek（带 tools 定义）→ 返回 tool_calls
#   3. tool_calls 非空 → 逐个执行工具 → 汇总结果
#   4. tool_calls 为空 → 纯聊天回复（或 query-knowledge 兜底）
#
# 降级策略：DeepSeek API 不可用时降级到本地 Qwen3:4b
# ============================================================================

import json
import logging
import urllib.request
from knowledge_wiki.config import settings
from knowledge_wiki.skill.tools import TOOLS, ROUTER_SYSTEM_PROMPT, execute_tool

_log = logging.getLogger(__name__)

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"


def route_intent(text: str, context: dict) -> dict:
    """LLM 驱动意图路由 — 返回 {'type': 'tool_calls'|'chat', ...}

    Args:
        text: 用户消息
        context: {'user_id': str, 'history': list, ...}

    Returns:
        {'type': 'tool_calls', 'calls': [{name, args, result}], 'reply': str}
        或 {'type': 'chat', 'reply': str}
    """
    history = context.get("history", [])
    user_id = context.get("user_id", "")

    # 构建 messages
    messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]

    # 注入历史（最近 10 轮）
    for m in history[-10:]:
        role = m.get("role", "user")
        content = m.get("content", "")[:500]
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": text})

    # 调用 DeepSeek function-calling
    tool_calls = _call_function_calling(messages)

    if not tool_calls:
        # 无工具调用 → 纯聊天或知识查询
        return _handle_chat(text, context, messages)

    # 有工具调用 → 逐个执行
    results = []
    for tc in tool_calls:
        name = tc.get("name", "")
        args = tc.get("arguments", {})
        try:
            result_text = execute_tool(name, args, context)
            results.append({"name": name, "args": args, "result": result_text})
        except Exception as e:
            _log.warning("Tool %s failed: %s", name, e)
            results.append({"name": name, "args": args, "result": f"执行失败: {e}"})

    # 将工具结果作为新的 assistant 消息
    if results:
        reply = _synthesize_reply(text, results, messages)
    else:
        reply = "操作完成"

    return {
        "type": "tool_calls",
        "calls": results,
        "reply": reply,
    }


def _handle_chat(text: str, context: dict, messages: list) -> dict:
    """无工具调用时的处理：纯聊天或知识查询."""
    # 默认走知识检索（知识库优先）
    try:
        from knowledge_wiki.wiki.retrieval.pipeline import run_pipeline_detailed
        result = run_pipeline_detailed(text)
        wiki_context = result["text"]
        has_relevant = result.get("has_relevant", True)

        if has_relevant:
            # 用 LLM 合成简短回复
            from knowledge_wiki.llm.deepseek import call_deepseek_query
            reply = call_deepseek_query(text, wiki_context[:6000])
            if reply:
                return {"type": "chat", "reply": reply, "source": "knowledge"}
            return {"type": "chat", "reply": wiki_context[:2800], "source": "raw"}

        # 无相关知识 → 通用回答
        reply = _call_deepseek_chat(messages)
        if reply:
            return {"type": "chat", "reply": reply, "source": "general"}
    except Exception:
        pass

    # 所有方案失败 → 降级到本地模型
    try:
        from knowledge_wiki.llm.ollama import call_detailed
        reply = call_detailed(text, "")
        if reply:
            return {"type": "chat", "reply": reply, "source": "local"}
    except Exception:
        pass

    return {"type": "chat", "reply": "你好！请问有什么可以帮你的？", "source": "fallback"}


def _synthesize_reply(original_text: str, tool_results: list, messages: list) -> str:
    """用 LLM 将工具结果合成为自然语言回复."""
    results_text = "\n".join(
        f"工具 {r['name']} 返回: {r['result'][:500]}"
        for r in tool_results
    )
    synth_messages = messages + [
        {"role": "assistant", "content": f"[工具调用已执行]\n{results_text}"},
        {"role": "user", "content": "请用中文给用户一个简洁的总结回复（1-3句话）。"},
    ]
    reply = _call_deepseek_chat(synth_messages, max_tokens=300)
    return reply if reply else results_text


# ---------------------------------------------------------------------------
# DeepSeek function-calling 调用
# ---------------------------------------------------------------------------

def _call_function_calling(messages: list[dict]) -> list[dict] | None:
    """调用 DeepSeek function-calling，返回 tool_calls 列表."""
    api_key = settings.deepseek_api_key
    if not api_key:
        _log.warning("DEEPSEEK_API_KEY not set, function-calling unavailable")
        return None

    for attempt in range(2):
        try:
            body = json.dumps({
                "model": settings.deepseek_model_ingest,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
                "temperature": 0.1,
                "max_tokens": 512,
            }).encode()

            req = urllib.request.Request(
                DEEPSEEK_API,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                choice = result["choices"][0]
                msg = choice.get("message", {})

                # 提取 tool_calls
                tool_calls_raw = msg.get("tool_calls", [])
                if not tool_calls_raw:
                    return None

                tool_calls = []
                for tc in tool_calls_raw:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    args_str = func.get("arguments", "{}")
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except json.JSONDecodeError:
                        args = {}
                    if name:
                        tool_calls.append({"name": name, "arguments": args})

                _log.info("Function calling: %s", [t["name"] for t in tool_calls])
                return tool_calls if tool_calls else None

        except Exception as e:
            if attempt < 1:
                _log.warning("Function calling retry %d: %s", attempt + 1, e)
            else:
                _log.error("Function calling failed: %s", e)
    return None


def _call_deepseek_chat(messages: list[dict], max_tokens: int = 500) -> str | None:
    """调用 DeepSeek 纯聊天（无 tools）."""
    api_key = settings.deepseek_api_key
    if not api_key:
        return None

    try:
        body = json.dumps({
            "model": settings.deepseek_model_ingest,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }).encode()

        req = urllib.request.Request(
            DEEPSEEK_API,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        _log.warning("DeepSeek chat failed: %s", e)
        return None
