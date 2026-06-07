"""todo-manage 技能实现 — 待办 CRUD（LLM 解析自然语言）."""

from datetime import datetime


def execute(context: dict) -> str:
    """LLM 解析意图 → 执行待办操作.

    context: input_text, user_id, send_md
    """
    from knowledge_wiki.skill.engine import classify_todo_action
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Todo

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    text = context.get("input_text", "").strip()

    # 去除触发词前缀
    for kw in ["待办", "todo", "任务"]:
        if text.lower().startswith(kw.lower()):
            text = text[len(kw):].strip()
            break

    if not text:
        return _list(user_id, send_md)

    # LLM 解析意图
    parsed = classify_todo_action(text)
    action = parsed.get("action", "create")

    if action == "list":
        return _list(user_id, send_md)

    elif action == "complete":
        return _complete(parsed.get("title", text), user_id, send_md)

    elif action == "delete":
        return _delete(parsed.get("title", text), user_id, send_md)

    else:  # create
        return _create(parsed, text, user_id, send_md)


def _create(parsed: dict, raw_text: str, user_id: str, send_md) -> str:
    """LLM 解析结果 → 创建待办."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Todo

    title = parsed.get("title", "")[:80]
    priority = parsed.get("priority", "medium")
    deadline = parsed.get("deadline")
    tags = parsed.get("tags", [])

    if not title:
        title = "未命名待办"

    conn = get_db()
    init_schema(conn)

    t = Todo(title=title, priority=priority, deadline=deadline, tags=tags,
             source="wecom" if user_id else "cli")
    d = t.to_dict()
    cols = ", ".join(d.keys())
    ph = ", ".join("?" for _ in d)
    conn.execute(f"INSERT INTO todos ({cols}) VALUES ({ph})", list(d.values()))
    conn.commit()
    conn.close()

    icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    msg = f"✅ 已创建待办：**{title}**"
    msg += f"\n优先级：{icons.get(priority, '⚪')} {priority}"
    if deadline:
        msg += f"\n截止：{deadline}"
    if tags:
        msg += f"\n标签：{', '.join(tags)}"

    # 从原文提取具体时间（LLM 只给日期，时间需要额外解析）
    trigger_time = _extract_time_from_text(raw_text, deadline)

    # 如果有截止日期或时间，自动创建提醒
    if deadline or trigger_time:
        try:
            from datetime import datetime
            from knowledge_wiki.assistant.db import get_db as _gdb, init_schema as _init
            from knowledge_wiki.assistant.models import Reminder
            from knowledge_wiki.assistant.scheduler import add_reminder_job

            # 确定提醒时间
            if trigger_time:
                reminder_dt = trigger_time
            elif deadline:
                reminder_dt = f"{deadline}T09:00"
            else:
                reminder_dt = None

            if reminder_dt:
                c2 = _gdb()
                _init(c2)
                r = Reminder(content=title, trigger_at=reminder_dt, user_id=user_id)
                rd = r.to_dict()
                cols2 = ", ".join(rd.keys())
                ph2 = ", ".join("?" for _ in rd)
                c2.execute(f"INSERT INTO reminders ({cols2}) VALUES ({ph2})", list(rd.values()))
                c2.commit()
                c2.close()

                add_reminder_job(r.id, title, reminder_dt, user_id=user_id)
                msg += f"\n⏰ 将在 {reminder_dt[:16]} 提醒"
        except Exception:
            pass  # 调度器未启动

    if send_md:
        send_md(user_id, msg[:3000])
    return msg


def _list(user_id: str, send_md) -> str:
    """列出待办."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Todo

    conn = get_db()
    init_schema(conn)
    rows = conn.execute(
        "SELECT * FROM todos WHERE status='pending' ORDER BY "
        "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
        "created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()

    if not rows:
        msg = '暂无待办。\n\n发送「待办 <内容>」来创建。'
    else:
        todos = [Todo.from_row(r) for r in rows]
        lines = [f"## 待办列表（{len(todos)} 项）", ""]
        icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        for i, t in enumerate(todos, 1):
            icon = icons.get(t.priority, "⚪")
            line = f"{i}. {icon} {t.title}"
            if t.deadline:
                line += f" | 📅 {t.deadline[:10]}"
            if t.tags:
                line += f" | {', '.join(t.tags[:3])}"
            lines.append(line)
        msg = "\n".join(lines)

    if send_md:
        send_md(user_id, msg[:3000])
    return msg


def _complete(keyword: str, user_id: str, send_md) -> str:
    """模糊匹配完成待办."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from datetime import datetime

    conn = get_db()
    init_schema(conn)
    rows = conn.execute(
        "SELECT * FROM todos WHERE status='pending' AND title LIKE ? LIMIT 3",
        [f"%{keyword}%"],
    ).fetchall()

    if not rows:
        conn.close()
        msg = f"未找到包含「{keyword}」的待办"
        if send_md:
            send_md(user_id, msg)
        return msg

    conn.execute(
        "UPDATE todos SET status='done', completed_at=?, updated_at=? WHERE id=?",
        [datetime.now().isoformat(), datetime.now().isoformat(), rows[0]["id"]],
    )
    conn.commit()
    conn.close()

    msg = f"🎉 已完成：**{rows[0]['title']}**"
    if send_md:
        send_md(user_id, msg)
    return msg


def _delete(keyword: str, user_id: str, send_md) -> str:
    """取消待办."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from datetime import datetime

    conn = get_db()
    init_schema(conn)
    rows = conn.execute(
        "SELECT * FROM todos WHERE status='pending' AND title LIKE ? LIMIT 3",
        [f"%{keyword}%"],
    ).fetchall()

    if not rows:
        conn.close()
        return f"未找到包含「{keyword}」的待办"

    conn.execute(
        "UPDATE todos SET status='cancelled', updated_at=? WHERE id=?",
        [datetime.now().isoformat(), rows[0]["id"]],
    )
    conn.commit()
    conn.close()

    msg = f"❌ 已取消：**{rows[0]['title']}**"
    if send_md:
        send_md(user_id, msg)
    return msg


def _extract_time_from_text(text: str, deadline: str | None) -> str | None:
    """从自然语言中提取具体时间，结合 deadline 生成 ISO 时间戳."""
    import re
    from datetime import datetime, timedelta

    now = datetime.now()
    hour = None
    minute = 0

    m = re.search(r"(上午|下午|晚上|中午)?(\d{1,2})[点:：](\d{0,2})?", text)
    if m:
        period = m.group(1) or ""
        hour = int(m.group(2))
        minute = int(m.group(3)) if m.group(3) else 0
        if "下午" in period and hour < 12:
            hour += 12
        elif "晚上" in period and hour < 12:
            hour += 12
        elif period == "上午" and hour == 12:
            hour = 0
        elif "中午" in period and hour < 12:
            hour += 12

    if hour is None:
        return None
    if hour > 23: hour = 23
    if minute > 59: minute = 59

    date_str = deadline if deadline else now.strftime("%Y-%m-%d")
    try:
        target_dt = datetime.fromisoformat(f"{date_str}T{hour:02d}:{minute:02d}:00")
        if target_dt <= now:
            target_dt += timedelta(days=1)
        return target_dt.isoformat()
    except (ValueError, TypeError):
        return f"{date_str}T{hour:02d}:{minute:02d}:00"
