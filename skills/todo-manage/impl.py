"""todo-manage 技能实现 — 待办 CRUD + 自然语言解析."""

import json
import re
from datetime import datetime, timedelta


def execute(context: dict) -> str:
    """解析用户意图，执行待办操作.

    context 需包含:
        input_text: 用户输入
        user_id: 企业微信用户 ID
        send_md: 发送 markdown 的函数（可选）
    """
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Todo

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    text = context.get("input_text", "").strip()

    # 去除触发词
    for kw in ["待办", "todo", "任务"]:
        if text.lower().startswith(kw.lower()):
            text = text[len(kw):].strip()
            break

    if not text:
        return _list_todos(user_id, send_md)

    # 意图分类
    if any(kw in text for kw in ["完成", "done", "搞定", "做了"]):
        return _complete_todo(text, user_id, send_md)
    elif any(kw in text for kw in ["取消", "删除", "删掉"]):
        return _delete_todo(text, user_id, send_md)
    elif any(kw in text for kw in ["有哪些", "列出", "查看", "待办列表", "列表"]):
        return _list_todos(user_id, send_md)
    else:
        return _create_todo(text, user_id, send_md)


def _create_todo(text: str, user_id: str, send_md) -> str:
    """从自然语言创建待办."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Todo

    title = text[:80]

    # 提取优先级
    priority = "medium"
    if any(kw in text for kw in ["高优先", "紧急", "重要", "high"]):
        priority = "high"
    elif any(kw in text for kw in ["低优先", "不急", "low"]):
        priority = "low"

    # 提取截止日期（简单模式匹配）
    deadline = _extract_deadline(text)

    # 提取标签（#xxx 或 @xxx）
    tags = re.findall(r"[#＃]([\w一-鿿]+)", text)
    # 清理标题中的标签和日期
    clean_title = re.sub(r"[#＃](\w+)|@(\w+)|(?:明天|今天|后天|下周|周[一二三四五六日])\S*", "", title).strip()
    if not clean_title:
        clean_title = text[:40]

    conn = get_db()
    init_schema(conn)

    todo = Todo(
        title=clean_title[:80],
        priority=priority,
        deadline=deadline,
        tags=tags,
        source="wecom" if user_id else "cli",
    )
    d = todo.to_dict()
    cols = ", ".join(d.keys())
    ph = ", ".join("?" for _ in d)
    conn.execute(f"INSERT INTO todos ({cols}) VALUES ({ph})", list(d.values()))
    conn.commit()
    conn.close()

    msg = f"✅ 已创建待办：**{clean_title}**"
    msg += f"\n优先级：{'🔴' if priority == 'high' else '🟡' if priority == 'medium' else '🟢'} {priority}"
    if deadline:
        msg += f"\n截止：{deadline[:10]}"
    if tags:
        msg += f"\n标签：{', '.join(tags)}"

    if send_md:
        send_md(user_id, msg)
    return msg


def _list_todos(user_id: str, send_md) -> str:
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
        msg = '暂无待办事项。\n\n发送「待办 <内容>」来创建第一条。'
    else:
        todos = [Todo.from_row(r) for r in rows]
        lines = ["## 待办列表", ""]
        for i, t in enumerate(todos, 1):
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t.priority, "⚪")
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


def _complete_todo(text: str, user_id: str, send_md) -> str:
    """模糊匹配并完成待办."""
    from knowledge_wiki.assistant.db import get_db, init_schema

    conn = get_db()
    init_schema(conn)

    # 模糊匹配：搜索标题包含关键词的待办
    keyword = text.replace("完成", "").replace("done", "").replace("搞定", "").strip()
    if not keyword:
        conn.close()
        msg = '请指定要完成的待办，如「完成 提交Q2报告」'
        if send_md:
            send_md(user_id, msg)
        return msg

    rows = conn.execute(
        "SELECT * FROM todos WHERE status='pending' AND title LIKE ? LIMIT 5",
        [f"%{keyword}%"],
    ).fetchall()

    if not rows:
        conn.close()
        msg = f"未找到包含「{keyword}」的待办"
        if send_md:
            send_md(user_id, msg)
        return msg

    # 如果只有一个匹配，直接完成
    if len(rows) == 1:
        conn.execute(
            "UPDATE todos SET status='done', completed_at=?, updated_at=? WHERE id=?",
            [datetime.now().isoformat(), datetime.now().isoformat(), rows[0]["id"]],
        )
        conn.commit()
        conn.close()
        msg = f"🎉 待办已完成：**{rows[0]['title']}**"
        if send_md:
            send_md(user_id, msg)
        return msg

    # 多个匹配，列出让用户选
    conn.close()
    lines = ["找到多个匹配，请指定：", ""]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. {r['title']}")
    msg = "\n".join(lines)
    if send_md:
        send_md(user_id, msg[:3000])
    return msg


def _delete_todo(text: str, user_id: str, send_md) -> str:
    """取消/删除待办."""
    from knowledge_wiki.assistant.db import get_db, init_schema

    conn = get_db()
    init_schema(conn)

    keyword = text.replace("取消", "").replace("删除", "").replace("删掉", "").strip()
    if not keyword:
        conn.close()
        return "请指定要取消的待办。"

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


def _extract_deadline(text: str) -> str | None:
    """从文本中提取截止日期."""
    today = datetime.now().date()

    if "明天" in text:
        d = today + timedelta(days=1)
        return d.isoformat()
    if "后天" in text:
        d = today + timedelta(days=2)
        return d.isoformat()
    if "今天" in text:
        return today.isoformat()

    # 匹配 YYYY-MM-DD 或 MM-DD
    m = re.search(r"(\d{4}-\d{2}-\d{2}|\d{2}-\d{2})", text)
    if m:
        ds = m.group(1)
        if len(ds) == 5:
            ds = f"{today.year}-{ds}"
        return ds

    # 匹配 X月X日
    m = re.search(r"(\d{1,2})月(\d{1,2})日?", text)
    if m:
        return f"{today.year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"

    return None
