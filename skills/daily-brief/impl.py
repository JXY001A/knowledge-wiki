"""daily-brief 技能实现 — 早报/晚报生成."""

from datetime import datetime


def execute(context: dict) -> str:
    """生成今日简报：待办 + 提醒 + 知识库动态."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Todo, Reminder

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    text = context.get("input_text", "").strip()

    is_evening = any(kw in text for kw in ["晚报", "晚上"])

    conn = get_db()
    init_schema(conn)

    today = datetime.now().date().isoformat()
    tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat() if not is_evening else today

    # 待办
    if is_evening:
        done = conn.execute("SELECT COUNT(*) FROM todos WHERE status='done'").fetchone()[0]
        pending = conn.execute(
            "SELECT * FROM todos WHERE status='pending' ORDER BY "
            "CASE priority WHEN 'high' THEN 0 ELSE 1 END LIMIT 8"
        ).fetchall()
    else:
        done = 0
        pending = conn.execute(
            "SELECT * FROM todos WHERE status='pending' "
            "AND (deadline >= ? OR deadline IS NULL) "
            "ORDER BY CASE priority WHEN 'high' THEN 0 ELSE 1 END LIMIT 8",
            [today],
        ).fetchall()

    # 提醒
    reminders = conn.execute(
        "SELECT * FROM reminders WHERE status='active' "
        "AND trigger_at BETWEEN ? AND ? ORDER BY trigger_at LIMIT 5",
        [today, today + "T23:59:59" if not tomorrow else tomorrow],
    ).fetchall()

    # 记忆统计
    try:
        from knowledge_wiki.memory.reader import get_stats
        mem_stats = get_stats()
    except Exception:
        mem_stats = {}

    conn.close()

    icon_map = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    brief_type = "晚报" if is_evening else "早报"
    lines = [f"## 📋 {datetime.now().strftime('%m月%d日')} {brief_type}", ""]

    # 待办
    lines.append(f"### {'今日完成' if is_evening else '今日待办'} ({len(pending)} 项)" if is_evening else f"### 今日待办 ({len(pending)} 项)")
    if pending:
        for r in pending:
            t = Todo.from_row(r)
            icon = icon_map.get(t.priority, "⚪")
            prefix = "✅" if is_evening and t.status == "done" else ""
            lines.append(f"- {prefix}{icon} {t.title}")
    else:
        lines.append("无")

    # 提醒
    if reminders:
        lines.append("")
        lines.append(f"### 今日提醒 ({len(reminders)} 个)")
        for r in reminders:
            rem = Reminder.from_row(r)
            time_str = rem.trigger_at[11:16] if len(rem.trigger_at) > 11 else ""
            lines.append(f"- ⏰ {time_str} {rem.content}")

    # 知识库动态
    if mem_stats.get("total", 0) > 0:
        lines.append("")
        lines.append("### 知识库动态")
        lines.append(f"- 总记录：{mem_stats.get('total', 0)} 条")
        last = mem_stats.get("last_event_summary", "")
        if last:
            lines.append(f"- 最近：{last[:60]}")

    msg = "\n".join(lines)

    from datetime import timedelta

    if send_md:
        send_md(user_id, msg[:3000])
    return msg
