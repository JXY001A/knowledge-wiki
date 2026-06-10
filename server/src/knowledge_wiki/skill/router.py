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
import re as _re_module
import urllib.request
from knowledge_wiki.config import settings
from knowledge_wiki.skill.tools import TOOLS, ROUTER_SYSTEM_PROMPT, execute_tool

_log = logging.getLogger(__name__)

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"

# ---------------------------------------------------------------------------
# 本地强信号路由 —— DeepSeek API 不可用时的快速通道
# 每项: (关键词列表, 工具名, 默认参数)
# 按列表顺序匹配，命中即停止
# ---------------------------------------------------------------------------
_LOCAL_ROUTES = [
    # —— 待办查看 ——
    (["查看待办", "待办列表", "我的待办", "有哪些待办", "列出待办", "待办事项",
      "待办", "todo list", "my todos", "有什么待办"], "manage_todos", {"action": "list"}),
    # —— 待办创建 ——
    (["加到待办", "加入到待办", "添加到待办", "记一个待办", "创建待办", "新建待办",
      "加一个待办", "弄到待办", "设为待办", "做待办", "建待办"], "manage_todos", {}),
    # —— 提醒我 + 活动 → 待办（非 remind） ——
    (["提醒我上班", "提醒我喝水", "提醒我开会", "提醒我提交", "提醒我完成",
      "提醒我打卡", "提醒我买", "提醒我吃药"], "manage_todos", {}),
    # —— 日程 ——
    (["今天要做什么", "今天有什么", "明天要做什么", "我的日程", "日程安排",
      "今天安排", "明天安排", "今日日程"], "view_schedule", {}),
    # —— 日报 ——
    (["早报", "晚报", "今日简报", "今天总结", "今日总结"], "generate_brief", {}),
    # —— 习惯打卡 ——
    (["打卡", "习惯打卡"], "track_habit", {"action": "stats"}),
    # —— 笔记 ——
    (["记一下", "记个笔记", "备忘", "闪念"], "quick_note", {}),
    # —— 书签 ——
    (["收藏链接", "收藏网址", "加个书签", "加书签"], "save_bookmark", {}),
    # —— 说/播放 ——
    (["说 ", "喊 ", "播放 ", "朗读 ", "speak ", "play "], "speak_text", {}),
]


def _match_local_route(text: str) -> tuple[str, dict] | None:
    """本地强信号匹配 —— 按关键词匹配，返回 (tool_name, default_args) 或 None."""
    for keywords, tool_name, default_args in _LOCAL_ROUTES:
        for kw in keywords:
            if kw in text:
                _log.info("Local route matched: %s → %s", kw, tool_name)
                return tool_name, dict(default_args)
    return None


def _enrich_args(text: str, tool_name: str, default_args: dict) -> dict:
    """从文本中提取参数，补充到 default_args。

    仅处理明确格式的命令，不猜测模糊意图。
    """
    args = dict(default_args)

    if tool_name == "manage_todos":
        if args.get("action") == "list":
            return args  # list 无需额外参数
        # create: 从"加到待办 xxx"中提取 title
        triggers = ["加到待办", "加入到待办", "添加到待办", "记一个待办", "创建待办",
                    "新建待办", "加一个待办", "弄到待办", "设为待办", "做待办", "建待办",
                    "提醒我上班", "提醒我喝水", "提醒我开会", "提醒我提交", "提醒我完成",
                    "提醒我打卡", "提醒我买", "提醒我吃药"]
        for t in triggers:
            if t in text:
                idx = text.find(t)
                suffix = text[idx + len(t):].strip()
                # 去除前导标点
                suffix = _re_module.sub(r'^[：:，,\s]+', '', suffix)
                if suffix:
                    args["action"] = "create"
                    args["title"] = suffix[:80]
                else:
                    args["action"] = "create"  # 无 title 时由 exec 提示
                return args
        args["action"] = "create"
        return args

    elif tool_name == "quick_note":
        triggers_note = ["记一下", "记个笔记", "备忘", "闪念"]
        for t in triggers_note:
            if t in text:
                idx = text.find(t)
                suffix = text[idx + len(t):].strip()
                suffix = _re_module.sub(r'^[：:，,\s]+', '', suffix)
                if suffix:
                    args["content"] = suffix[:2000]
                return args
        return args

    elif tool_name == "save_bookmark":
        # 从"收藏链接 https://xxx"中提取 URL
        url_match = _re_module.search(r'https?://[^\s]+', text)
        if url_match:
            args["url"] = url_match.group(0)
        return args

    elif tool_name == "speak_text":
        triggers_speak = ["说 ", "喊 ", "播放 ", "朗读 ", "speak ", "play "]
        for t in triggers_speak:
            if text.startswith(t):
                args["text"] = text[len(t):].strip()
                return args
            if t in text:
                idx = text.find(t)
                suffix = text[idx + len(t):].strip()
                if suffix:
                    args["text"] = suffix
                return args
        return args

    return args


def route_intent(text: str, context: dict) -> dict:
    """LLM 驱动意图路由 — 返回 {'type': 'tool_calls'|'chat', ...}

    三层策略:
      1. 本地强信号预检 —— 关键词命中直接路由（零 API 调用）
      2. DeepSeek function-calling —— 复杂意图智能路由
      3. 知识检索降级 —— 都失败时走知识库

    Args:
        text: 用户消息
        context: {'user_id': str, 'history': list, ...}

    Returns:
        {'type': 'tool_calls', 'calls': [{name, args, result}], 'reply': str}
        或 {'type': 'chat', 'reply': str}
    """
    history = context.get("history", [])
    user_id = context.get("user_id", "")

    # ---- 第 0 层: 本地强信号快速通道 ----
    local_hit = _match_local_route(text)
    if local_hit:
        tool_name, default_args = local_hit
        # 尝试用 LLM 补充参数（如从文本中提取 title）
        args = _enrich_args(text, tool_name, default_args)
        try:
            result_text = execute_tool(tool_name, args, context)
            return {
                "type": "tool_calls",
                "calls": [{"name": tool_name, "args": args, "result": result_text}],
                "reply": result_text,
            }
        except Exception as e:
            _log.warning("Local route %s failed: %s, falling back to LLM", tool_name, e)
            # 本地路由执行失败，继续走 LLM

    # 构建 messages
    messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]

    # 注入历史（最近 10 轮）
    for m in history[-10:]:
        role = m.get("role", "user")
        content = m.get("content", "")[:500]
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": text})

    # ---- 第 1 层: DeepSeek function-calling ----
    tool_calls = _call_function_calling(messages)

    if not tool_calls:
        # ---- 第 2 层: 知识检索降级 ----
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

    # 展示结果：list/view 类直接展示原始结果，create/delete 类才合成简短回复
    display_tools = {"manage_todos": ["list"], "view_schedule": None, "track_habit": ["stats"],
                     "generate_brief": None, "search_knowledge": None}
    if results:
        # 判断是否直接展示原始结果（不压缩）
        direct = any(
            r["name"] in display_tools
            and (display_tools[r["name"]] is None or r.get("args", {}).get("action") in display_tools[r["name"]])
            for r in results
        )
        if direct and len(results) == 1:
            reply = results[0]["result"]
        else:
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
                "max_tokens": 1024,
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
