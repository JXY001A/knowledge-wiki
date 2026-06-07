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
        return _create(parsed, user_id, send_md)


def _create(parsed: dict, user_id: str, send_md) -> str:
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
