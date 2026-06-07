"""habit-track 技能实现 — 习惯打卡追踪."""

import re
from datetime import datetime


def execute(context: dict) -> str:
    """打卡记录或查看习惯统计."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Habit, HabitLog

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    text = context.get("input_text", "").strip()

    # 去除触发词
    for kw in ["打卡", "习惯", "habit"]:
        if kw in text[:6]:
            text = text.replace(kw, "", 1).strip()
            break

    today_str = datetime.now().strftime("%Y-%m-%d")

    # 判断意图：查看统计 vs 打卡
    if any(kw in text for kw in ["统计", "进度", "查看", "情况"]):
        return _show_stats(user_id, send_md)
    elif not text:
        return _show_stats(user_id, send_md)
    else:
        return _do_checkin(text, today_str, user_id, send_md)


def _do_checkin(text: str, today_str: str, user_id: str, send_md) -> str:
    """执行打卡."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Habit, HabitLog

    conn = get_db()
    init_schema(conn)

    # 尝试匹配已有习惯
    habit_rows = conn.execute(
        "SELECT * FROM habits WHERE archived_at IS NULL"
    ).fetchall()
    habits = [Habit.from_row(r) for r in habit_rows]

    # 模糊匹配习惯名
    matched = None
    for h in habits:
        if h.name in text:
            matched = h
            break

    if not matched:
        # 创建新习惯
        name = text[:20]
        if not name:
            conn.close()
            return "请指定习惯名称。用法：打卡 喝水"

        habit = Habit(name=name)
        hd = habit.to_dict()
        cols = ", ".join(hd.keys())
        ph = ", ".join("?" for _ in hd)
        conn.execute(f"INSERT INTO habits ({cols}) VALUES ({ph})", list(hd.values()))
        conn.commit()
        matched = Habit.from_row(
            conn.execute("SELECT * FROM habits WHERE name=?", [name]).fetchone()
        )

    # 记录打卡
    # 提取数值（如 "喝水 8杯" → 8）
    value = 1.0
    num_match = re.search(r"(\d+(?:\.\d+)?)", text)
    if num_match:
        value = float(num_match.group(1))

    try:
        log = HabitLog(habit_id=matched.id, date=today_str, value=value)
        ld = log.to_dict()
        cols = ", ".join(ld.keys())
        ph = ", ".join("?" for _ in ld)
        conn.execute(
            f"INSERT INTO habit_logs ({cols}) VALUES ({ph})", list(ld.values())
        )
        conn.commit()
        unit = matched.unit or "次"
        msg = f"✅ 打卡成功：{matched.name} {value}{'杯' if matched.unit == 'count' else unit}"
    except Exception:
        msg = f"⏭️ 今日已打卡：{matched.name}"

    conn.close()

    if send_md:
        send_md(user_id, msg)
    return msg


def _show_stats(user_id: str, send_md) -> str:
    """显示习惯统计."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Habit

    conn = get_db()
    init_schema(conn)

    habits = [Habit.from_row(r) for r in conn.execute(
        "SELECT * FROM habits WHERE archived_at IS NULL"
    ).fetchall()]

    if not habits:
        conn.close()
        msg = '暂无习惯记录。\n\n发送「打卡 <习惯名>」开始记录！'
        if send_md:
            send_md(user_id, msg)
        return msg

    lines = ["## 习惯追踪", ""]
    for h in habits:
        # 本周完成次数
        week_count = conn.execute(
            "SELECT COUNT(*) FROM habit_logs WHERE habit_id=? AND date >= date('now', '-7 days')",
            [h.id],
        ).fetchone()[0]
        # 连续天数
        streak = _calc_streak(conn, h.id)
        target = f"/{h.target}" if h.target else ""
        lines.append(f"- {h.name}: 本周 {week_count}{target} | 🔥 {streak} 天连续")

    conn.close()
    msg = "\n".join(lines)

    if send_md:
        send_md(user_id, msg[:3000])
    return msg


def _calc_streak(conn, habit_id: str) -> int:
    """计算连续打卡天数."""
    from datetime import datetime, timedelta
    today = datetime.now().date()
    streak = 0
    for i in range(365):
        d = (today - timedelta(days=i)).isoformat()
        row = conn.execute(
            "SELECT COUNT(*) FROM habit_logs WHERE habit_id=? AND date=?",
            [habit_id, d],
        ).fetchone()
        if row and row[0] > 0:
            streak += 1
        elif i == 0:
            continue  # 今天没打卡不算断
        else:
            break
    return streak
