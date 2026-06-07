"""schedule-view 技能实现 — 查看今日/明日日程."""

import re
from datetime import datetime, timedelta


def execute(context: dict) -> str:
    """查看日程：今日待办 + 今日提醒 + 即将到期.

    context 需包含:
        input_text: 用户输入
        user_id: 用户 ID
        send_md: 回复回调
    """
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Todo, Reminder

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    text = context.get("input_text", "").strip()

    # 判断查询日期
    today = datetime.now().date()
    target_date = today
    if "明天" in text:
        target_date = today + timedelta(days=1)
    elif "后天" in text:
        target_date = today + timedelta(days=2)

    date_str = target_date.isoformat()
    next_date = (target_date + timedelta(days=1)).isoformat()

    conn = get_db()
    init_schema(conn)

    # 查询待办
    todo_rows = conn.execute(
        "SELECT * FROM todos WHERE status='pending' "
        "AND (deadline BETWEEN ? AND ? OR deadline IS NULL) "
        "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
        "created_at DESC",
        [date_str, next_date],
    ).fetchall()

    # 查询提醒
    reminder_rows = conn.execute(
        "SELECT * FROM reminders WHERE status='active' "
        "AND trigger_at BETWEEN ? AND ? "
        "ORDER BY trigger_at",
        [date_str, next_date],
    ).fetchall()

    # 当天之前未完成的待办（过期）
    overdue_rows = conn.execute(
        "SELECT * FROM todos WHERE status='pending' AND deadline < ? "
        "ORDER BY deadline ASC LIMIT 10",
        [date_str],
    ).fetchall()

    conn.close()

    # 组装回复
    date_label = f"{target_date.month}月{target_date.day}日"
    if target_date == today:
        date_label += "（今天）"
    elif target_date == today + timedelta(days=1):
        date_label += "（明天）"

    lines = [f"## 📅 {date_label}", ""]

    # 当日待办
    lines.append("### 待办事项")
    if todo_rows:
        icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        for i, r in enumerate(todo_rows, 1):
            t = Todo.from_row(r)
            icon = icons.get(t.priority, "⚪")
            line = f"{i}. {icon} {t.title}"
            if t.deadline:
                dl = t.deadline[:10] if t.deadline else ""
                if dl == date_str:
                    line += " ⚠️ 今天截止"
            lines.append(line)
    else:
        lines.append("无待办")

    # 当日提醒
    lines.append("")
    lines.append("### 定时提醒")
    if reminder_rows:
        for r in reminder_rows:
            rem = Reminder.from_row(r)
            try:
                t = datetime.fromisoformat(rem.trigger_at).strftime("%H:%M")
            except (ValueError, TypeError):
                t = ""
            lines.append(f"- ⏰ {t} {rem.content}")
    else:
        lines.append("无提醒")

    # 过期待办
    if overdue_rows:
        lines.append("")
        lines.append("### ⚠️ 逾期未完成")
        for r in overdue_rows[:5]:
            t = Todo.from_row(r)
            dl = t.deadline[:10] if t.deadline else "?"
            lines.append(f"- {t.title}（截止 {dl}）")

    msg = "\n".join(lines)

    if send_md:
        send_md(user_id, msg[:3000])
    return msg
