# ============================================================================
# 工具定义 + 统一执行器 — LLM function-calling 的 JSON Schema 层
# ============================================================================
# 每个 skill 在此注册为一个 tool definition，Router 将全部 tools 发给 LLM，
# LLM 根据用户消息自行选择调用哪些工具。
#
# 设计原则：
#   1. 每个 tool 对应一个现有 skill，不重复实现
#   2. JSON Schema 描述清晰，LLM 能准确理解何时调用
#   3. 统一 execute() 桥接到各 skill 的 context dict
# ============================================================================

import logging

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工具定义（OpenAI/DeepSeek function-calling 格式）
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "搜索个人知识库，获取相关知识。当用户询问概念、技术问题、需要查资料时调用。"
                           "也用于需要基于知识库内容回答的任何问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询词或问题，如'DeepSeek 模型列表'、'MCP 协议定义'",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_todos",
            "description": "管理待办事项：创建、查看、完成、删除。用户提到要做某事、创建任务、查看待办列表时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "complete", "delete"],
                        "description": "操作类型：create=创建新待办, list=查看列表, complete=完成, delete=删除",
                    },
                    "title": {
                        "type": "string",
                        "description": "待办标题（create/complete/delete 时需要）",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "优先级（仅 create），默认 medium",
                    },
                    "deadline": {
                        "type": "string",
                        "description": "截止时间 ISO8601 格式，如 2026-06-11T15:00（仅 create）",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "设置定时提醒。用户说'提醒我''设个闹钟''到时间叫我'时调用。"
                           "支持具体时间如'下午3点'、相对时间如'明天9点'。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "提醒内容，如'提交周报'、'开会'",
                    },
                    "trigger_at": {
                        "type": "string",
                        "description": "触发时间 ISO8601，如 2026-06-11T15:00:00",
                    },
                    "recurrence": {
                        "type": "string",
                        "description": "重复规则（可选）：daily/weekly/monthly，无则一次性",
                    },
                },
                "required": ["content", "trigger_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ingest_url",
            "description": "摄取网页到个人知识库。用户发送URL或说'分析这篇文章''收藏这个链接'时调用。"
                           "下载网页→AI分析→生成wiki页面→存入知识库。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要摄取的网页 URL",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quick_note",
            "description": "快速记录笔记。用户说'记一下''备忘''闪念'时调用。"
                           "自动提取标签并保存到数据库。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "笔记内容",
                    },
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_bookmark",
            "description": "保存网页书签。用户说'收藏''加书签''保存链接'时调用。"
                           "自动提取标题和标签。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "书签 URL",
                    },
                    "title": {
                        "type": "string",
                        "description": "书签标题（可选，不填则自动提取）",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_schedule",
            "description": "查看今日日程安排。用户问'今天有什么''我的日程''今天要做什么'时调用。"
                           "返回待办+提醒+即将到期。",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "查看日期（可选，默认今天）。格式 YYYY-MM-DD",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "track_habit",
            "description": "习惯打卡或查看统计。用户说'打卡''习惯''坚持''签到'时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["checkin", "stats", "create"],
                        "description": "checkin=打卡, stats=查看统计, create=创建新习惯",
                    },
                    "name": {
                        "type": "string",
                        "description": "习惯名称（checkin/create 时需要）",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_brief",
            "description": "生成每日早报或晚报。用户说'早报''晚报''今日简报''今天总结'时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["morning", "evening"],
                        "description": "早报或晚报，根据时间自动判断",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "speak_text",
            "description": "通过语音朗读文字。用户说'说''朗读''播放'后跟内容时调用。"
                           "使用服务器 USB 音响播放 TTS 合成语音。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要朗读的文字内容",
                    },
                },
                "required": ["text"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# 工具执行器 — 桥接到现有 skill
# ---------------------------------------------------------------------------

def execute_tool(name: str, arguments: dict, context: dict) -> str:
    """执行指定工具，返回结果文本。

    Args:
        name: 工具名（与 TOOLS 定义一致）
        arguments: LLM 提取的参数
        context: 原始请求上下文（user_id, send_md, send_tpl, history 等）

    Returns:
        工具执行结果（markdown 格式文本）
    """
    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    send_tpl = context.get("send_tpl")

    _log.info("Tool call: %s(%s)", name, {k: str(v)[:60] for k, v in arguments.items()})

    if name == "search_knowledge":
        return _exec_search_knowledge(arguments, context)

    elif name == "manage_todos":
        return _exec_manage_todos(arguments, user_id, send_md)

    elif name == "set_reminder":
        return _exec_set_reminder(arguments, user_id, send_md)

    elif name == "ingest_url":
        return _exec_ingest_url(arguments, user_id, send_md)

    elif name == "quick_note":
        return _exec_quick_note(arguments, user_id, send_md)

    elif name == "save_bookmark":
        return _exec_save_bookmark(arguments, user_id, send_md)

    elif name == "view_schedule":
        return _exec_view_schedule(arguments, user_id, send_md)

    elif name == "track_habit":
        return _exec_track_habit(arguments, user_id, send_md)

    elif name == "generate_brief":
        return _exec_generate_brief(arguments, user_id, send_md)

    elif name == "speak_text":
        return _exec_speak_text(arguments, user_id, send_md)

    else:
        return f"未知工具: {name}"


# ---- 各工具实现 ----

def _exec_search_knowledge(args: dict, ctx: dict) -> str:
    """搜索知识库."""
    query = args.get("query", "").strip()
    if not query:
        return "请输入搜索内容"

    from knowledge_wiki.wiki.retrieval.pipeline import run_pipeline_detailed
    result = run_pipeline_detailed(query)
    wiki_context = result["text"]
    has_relevant = result.get("has_relevant", True)

    if not has_relevant:
        return f"⚠️ 知识库暂无直接覆盖「{query}」的资料。\n\n{wiki_context[:500]}"

    # 用 DeepSeek 合成回答
    from knowledge_wiki.llm.deepseek import call_deepseek_query
    answer = call_deepseek_query(query, wiki_context[:6000])
    if answer:
        return answer
    return wiki_context[:2800]


def _exec_manage_todos(args: dict, user_id: str, send_md) -> str:
    """执行待办操作 — 桥接到 todo-manage skill."""
    action = args.get("action", "list")
    title = args.get("title", "")
    priority = args.get("priority", "medium")
    deadline = args.get("deadline")

    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Todo
    from datetime import datetime

    if action == "list":
        conn = get_db()
        init_schema(conn)
        today = datetime.now().strftime("%Y-%m-%d")
        # 排序：逾期 > 今天到期 > 本周 > 其他
        rows = conn.execute(
            "SELECT * FROM todos WHERE status='pending' ORDER BY "
            "CASE WHEN deadline < ? THEN 0 WHEN deadline = ? THEN 1 "
            "WHEN deadline <= date('now','+7 days') THEN 2 ELSE 3 END, "
            "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END "
            "LIMIT 20",
            [today, today],
        ).fetchall()
        conn.close()

        if not rows:
            return "📋 暂无待办。发送「待办 内容」来创建。"
        todos = [Todo.from_row(r) for r in rows]
        lines = [f"## 📋 待办列表（{len(todos)} 项）", ""]
        for i, t in enumerate(todos, 1):
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t.priority, "⚪")
            overdue = t.deadline and t.deadline < today
            today_due = t.deadline and t.deadline[:10] == today
            extra = " ⚠️逾期" if overdue else (" 📅今天" if today_due else "")
            line = f"{i}. {icon} {t.title}{extra}"
            if t.deadline:
                line += f" | {t.deadline[:10]}"
            lines.append(line)
        return "\n".join(lines)

    elif action == "create":
        if not title:
            return "请提供待办标题"
        conn = get_db()
        init_schema(conn)
        t = Todo(title=title[:80], priority=priority, deadline=deadline,
                 tags=[], source="llm_router")
        d = t.to_dict()
        cols = ", ".join(d.keys())
        ph = ", ".join("?" for _ in d)
        conn.execute(f"INSERT INTO todos ({cols}) VALUES ({ph})", list(d.values()))
        conn.commit()
        conn.close()
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
        msg = f"✅ 已创建待办：{icon} **{title}**"
        if deadline:
            msg += f"\n⏰ 截止：{deadline[:16]}"
        return msg

    elif action == "complete":
        if not title:
            return "请指定要完成的待办"
        conn = get_db()
        init_schema(conn)
        rows = conn.execute(
            "SELECT * FROM todos WHERE status='pending' AND title LIKE ? LIMIT 3",
            [f"%{title}%"],
        ).fetchall()
        if not rows:
            conn.close()
            return f"未找到包含「{title}」的待办"
        conn.execute(
            "UPDATE todos SET status='done', completed_at=?, updated_at=? WHERE id=?",
            [datetime.now().isoformat(), datetime.now().isoformat(), rows[0]["id"]],
        )
        conn.commit()
        conn.close()
        return f"🎉 已完成：**{rows[0]['title']}**"

    elif action == "delete":
        if not title:
            return "请指定要删除的待办"
        conn = get_db()
        init_schema(conn)
        rows = conn.execute(
            "SELECT * FROM todos WHERE status='pending' AND title LIKE ? LIMIT 3",
            [f"%{title}%"],
        ).fetchall()
        if not rows:
            conn.close()
            return f"未找到包含「{title}」的待办"
        conn.execute(
            "UPDATE todos SET status='cancelled', updated_at=? WHERE id=?",
            [datetime.now().isoformat(), rows[0]["id"]],
        )
        conn.commit()
        conn.close()
        return f"❌ 已取消：**{rows[0]['title']}**"

    return "未知操作"


def _exec_set_reminder(args: dict, user_id: str, send_md) -> str:
    """设置提醒."""
    content = args.get("content", "")
    trigger_at = args.get("trigger_at", "")
    if not content or not trigger_at:
        return "请提供提醒内容和时间"

    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Reminder

    conn = get_db()
    init_schema(conn)
    r = Reminder(content=content[:200], trigger_at=trigger_at, user_id=user_id)
    d = r.to_dict()
    cols = ", ".join(d.keys())
    ph = ", ".join("?" for _ in d)
    conn.execute(f"INSERT INTO reminders ({cols}) VALUES ({ph})", list(d.values()))
    conn.commit()
    conn.close()

    # threading.Timer 推送
    try:
        from agent.skills.remind_set.impl import _schedule_push
        _schedule_push(r.id, content, trigger_at, user_id)
    except ImportError:
        pass

    try:
        from datetime import datetime
        dt = datetime.fromisoformat(trigger_at)
        time_str = dt.strftime("%m月%d日 %H:%M")
    except Exception:
        time_str = trigger_at[:16]
    return f"⏰ 已设置提醒\n**{content}**\n时间：{time_str}"


def _exec_ingest_url(args: dict, user_id: str, send_md) -> str:
    """摄取 URL."""
    url = args.get("url", "").strip()
    if not url:
        return "请提供要摄取的 URL"
    # 复用现有 ingest-article 技能
    try:
        ctx = {"user_id": user_id, "input_text": url, "send_md": send_md}
        from agent.skills.ingest_article.impl import execute as ingest_exec
        return ingest_exec(ctx)
    except ImportError:
        # Fallback: 直接调用 webhook processor
        from knowledge_wiki.webhook.process import fetch_url_text
        from knowledge_wiki.llm.deepseek import call_ingest
        from knowledge_wiki.wiki.builder import build_source_page
        from knowledge_wiki.wiki.git import commit_and_push
        raw_text = fetch_url_text(url)
        if not raw_text:
            return f"❌ 无法下载 {url}"
        llm_data = call_ingest(raw_text, url)
        if not llm_data:
            return f"❌ LLM 分析失败"
        build_source_page(llm_data, url)
        commit_and_push(f"ingest: {llm_data.get('title', url[:60])}")
        return f"✅ 已摄取：**{llm_data.get('title', url[:60])}**\n{llm_data.get('summary', '')}"


def _exec_quick_note(args: dict, user_id: str, send_md) -> str:
    """快速笔记."""
    content = args.get("content", "").strip()
    if not content:
        return "请输入笔记内容"
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Note
    conn = get_db()
    init_schema(conn)
    n = Note(content=content[:2000], user_id=user_id or "system")
    d = n.to_dict()
    cols = ", ".join(d.keys())
    ph = ", ".join("?" for _ in d)
    conn.execute(f"INSERT INTO notes ({cols}) VALUES ({ph})", list(d.values()))
    conn.commit()
    conn.close()
    return f"📝 已保存笔记（{len(content)} 字）"


def _exec_save_bookmark(args: dict, user_id: str, send_md) -> str:
    """保存书签."""
    url = args.get("url", "").strip()
    title = args.get("title", "").strip()
    if not url:
        return "请提供书签 URL"
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Bookmark
    conn = get_db()
    init_schema(conn)
    b = Bookmark(url=url, title=title or url[:80], user_id=user_id or "system")
    d = b.to_dict()
    cols = ", ".join(d.keys())
    ph = ", ".join("?" for _ in d)
    conn.execute(f"INSERT INTO bookmarks ({cols}) VALUES ({ph})", list(d.values()))
    conn.commit()
    conn.close()
    return f"🔖 已保存书签：**{title or url[:60]}**"


def _exec_view_schedule(args: dict, user_id: str, send_md) -> str:
    """查看日程 — 桥接到 schedule-view skill."""
    try:
        ctx = {"user_id": user_id, "input_text": "日程", "send_md": send_md}
        from agent.skills.schedule_view.impl import execute as sched_exec
        return sched_exec(ctx)
    except ImportError:
        return "日程功能暂不可用"


def _exec_track_habit(args: dict, user_id: str, send_md) -> str:
    """习惯打卡."""
    action = args.get("action", "stats")
    name = args.get("name", "")
    from knowledge_wiki.assistant.db import get_db, init_schema
    conn = get_db()
    init_schema(conn)
    if action == "stats":
        rows = conn.execute(
            "SELECT * FROM habits WHERE status='active' ORDER BY streak DESC LIMIT 10"
        ).fetchall()
        conn.close()
        if not rows:
            return "暂无习惯记录。发送「打卡 习惯名」开始。"
        lines = ["## 🔥 习惯统计", ""]
        for r in rows:
            emoji = "🔥" if r["streak"] >= 7 else "⭐" if r["streak"] >= 3 else "🌱"
            lines.append(f"- {emoji} {r['name']}（连续 {r['streak']} 天）")
        return "\n".join(lines)
    elif action == "checkin":
        if not name:
            return "请指定习惯名称"
        # 查找或创建习惯
        row = conn.execute("SELECT * FROM habits WHERE name=? LIMIT 1", [name]).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO habits (name,status,streak,created_at) VALUES (?,?,?,?)",
                [name, "active", 0, __import__("datetime").datetime.now().isoformat()],
            )
            conn.commit()
            row = conn.execute("SELECT * FROM habits WHERE name=? LIMIT 1", [name]).fetchone()
        # 检测今天是否已打卡
        today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
        existing = conn.execute(
            "SELECT * FROM habit_logs WHERE habit_id=? AND date=? LIMIT 1",
            [row["id"], today],
        ).fetchone()
        if existing:
            conn.close()
            return f"✅ 今天已打卡「{name}」"
        # 记录打卡
        conn.execute(
            "INSERT INTO habit_logs (habit_id,date,created_at) VALUES (?,?,?)",
            [row["id"], today, __import__("datetime").datetime.now().isoformat()],
        )
        conn.execute(
            "UPDATE habits SET streak=streak+1, last_checkin=? WHERE id=?",
            [today, row["id"]],
        )
        conn.commit()
        conn.close()
        return f"✅ 已打卡「{name}」🔥 连续 {row['streak'] + 1} 天！"
    elif action == "create":
        if not name:
            return "请提供习惯名称"
        conn.execute(
            "INSERT INTO habits (name,status,streak,created_at) VALUES (?,?,?,?)",
            [name, "active", 0, __import__("datetime").datetime.now().isoformat()],
        )
        conn.commit()
        conn.close()
        return f"✅ 已创建习惯：**{name}**"
    return "未知操作"


def _exec_generate_brief(args: dict, user_id: str, send_md) -> str:
    """生成日报."""
    try:
        brief_type = args.get("type", "morning")
        ctx = {"user_id": user_id, "input_text": "早报" if brief_type == "morning" else "晚报",
               "send_md": send_md}
        from agent.skills.daily_brief.impl import execute as brief_exec
        return brief_exec(ctx)
    except ImportError:
        return "日报功能暂不可用"


def _exec_speak_text(args: dict, user_id: str, send_md) -> str:
    """TTS 语音朗读."""
    text = args.get("text", "").strip()
    if not text:
        return "请输入要朗读的内容"
    try:
        ctx = {"user_id": user_id, "input_text": f"说 {text}", "send_md": send_md}
        from agent.skills.speak_text.impl import execute as speak_exec
        return speak_exec(ctx)
    except ImportError:
        return "语音功能暂不可用"


# ---------------------------------------------------------------------------
# 生成 System Prompt
# ---------------------------------------------------------------------------

ROUTER_SYSTEM_PROMPT = """你是个人 AI 助手。你拥有工具可以执行实际操作，不仅仅是聊天。

**核心原则：优先调用工具！** 如果用户表达了任何操作意图，必须先调用对应工具，而不是直接聊天回复。

**必须调用工具的场景（按优先级）**:
1. 用户提到具体任务/安排/要做的事 → manage_todos (action=create)
   示例: "帮我记下明天开会" → manage_todos
   示例: "我要买牛奶" → manage_todos
   示例: "待办列表" → manage_todos(action=list)
2. 用户提到时间+事件 → set_reminder
   示例: "明天下午3点提醒我开会" → set_reminder
   示例: "每天9点提醒我喝水" → set_reminder
3. 用户发 URL → ingest_url
4. 用户问知识/概念/技术问题 → search_knowledge
5. 用户说"记一下""备忘""笔记" → quick_note
6. 用户说"收藏""书签" → save_bookmark
7. 用户问"今天有什么""日程" → view_schedule
8. 用户说"打卡""习惯" → track_habit
9. 用户说"早报""晚报""今日总结" → generate_brief
10. 用户说"说""朗读""播放"+内容 → speak_text

**可以同时调用多个工具！**
- "帮我记下明天下午3点开会" → 同时调用 manage_todos(create) + set_reminder
- "查看待办并生成早报" → 同时调用 manage_todos(list) + generate_brief

**不要调用工具的场景**:
- 纯问候/聊天/感谢
- 没有任何操作意图的闲聊

**回复风格**: 工具执行后，用一句话确认完成。中文，简洁。
不用工具时，简短友好地回复。"""
