"""remind-set 技能实现 — 定时提醒设置 + threading.Timer 推送."""

import re
import threading
from datetime import datetime, timedelta, timezone


def execute(context: dict) -> str:
    """解析用户意图，设置定时提醒并通过 threading.Timer 推送."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Reminder

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    text = context.get("input_text", "").strip()

    for kw in ["提醒", "闹钟", "定时", "叫我", "记得", "别忘"]:
        if kw in text[:6]:
            text = text.replace(kw, "", 1).strip()
            break

    if not text:
        msg = "请指定提醒内容和时间。\n\n用法：提醒 <内容> <时间>"
        if send_md:
            send_md(user_id, msg)
        return msg

    trigger_at, content = _parse_reminder(text)
    if not trigger_at:
        msg = "无法识别时间。\n格式：提醒 下午3点 code review"
        if send_md:
            send_md(user_id, msg)
        return msg

    # 写入数据库
    conn = get_db()
    init_schema(conn)
    r = Reminder(content=content[:200], trigger_at=trigger_at, user_id=user_id)
    d = r.to_dict()
    cols = ", ".join(d.keys())
    ph = ", ".join("?" for _ in d)
    conn.execute(f"INSERT INTO reminders ({cols}) VALUES ({ph})", list(d.values()))
    conn.commit()
    conn.close()

    # threading.Timer 直接推送（不依赖 scheduler 进程）
    _schedule_push(r.id, content, trigger_at, user_id)

    try:
        dt = datetime.fromisoformat(trigger_at)
        time_str = dt.strftime("%m月%d日 %H:%M")
    except (ValueError, TypeError):
        time_str = trigger_at[:16]

    msg = f"⏰ 已设置提醒\n\n**{content}**\n时间：{time_str}"
    if send_md:
        send_md(user_id, msg[:3000])
    return msg


def _schedule_push(reminder_id: str, content: str, trigger_at: str, user_id: str):
    """用 threading.Timer 定时推送."""
    try:
        trigger_dt = datetime.fromisoformat(trigger_at)
        now_utc = datetime.now(timezone.utc)
        delay = (trigger_dt - now_utc).total_seconds()
    except (ValueError, TypeError):
        return

    if delay <= 0:
        return

    def _push():
        try:
            from knowledge_wiki.webhook.wechat.api import send_markdown
            from knowledge_wiki.assistant.db import get_db, init_schema

            msg = "⏰ **提醒**\n\n" + content
            ok = send_markdown(user_id, msg)

            conn = get_db()
            init_schema(conn)
            conn.execute(
                "UPDATE reminders SET status=?, fired_at=? WHERE id=?",
                ["fired" if ok else "active", datetime.now().isoformat(), reminder_id],
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    timer = threading.Timer(delay, _push)
    timer.daemon = True
    timer.start()


def _parse_reminder(text: str) -> tuple[str | None, str]:
    """从自然语言中解析时间和内容."""
    now = datetime.now()

    time_patterns = [
        (r"(上午|下午|晚上|中午)?(\d{1,2})[点:：](\d{0,2})?", _parse_cn_time),
        (r"(\d{1,2}):(\d{2})", _parse_24h_time),
        (r"(明天|后天|今天)", _parse_relative_day),
    ]

    trigger_at = None
    for pattern, parser in time_patterns:
        m = re.search(pattern, text)
        if m:
            result = parser(now, m)
            if result:
                trigger_at = result
                break

    content = text
    if trigger_at:
        content = re.sub(r"(上午|下午|晚上|中午)?\d{1,2}[点:：]\d{0,2}分?", "", content)
        content = re.sub(r"\d{1,2}:\d{2}", "", content)
        content = re.sub(r"明天|后天|今天", "", content)
        content = content.strip()

    return trigger_at, content if content else text


def _parse_cn_time(now: datetime, m: re.Match) -> str | None:
    period = m.group(1) or ""
    hour = int(m.group(2))
    minute = int(m.group(3)) if m.group(3) else 0
    if "下午" in period and hour < 12:
        hour += 12
    elif "晚上" in period and hour < 12:
        hour += 12
    elif "上午" in period and hour == 12:
        hour = 0
    elif "中午" in period and hour < 12:
        hour += 12
    if hour > 23: hour = 23
    if minute > 59: minute = 59
    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if dt <= now:
        dt += timedelta(days=1)
    return dt.isoformat()


def _parse_24h_time(now: datetime, m: re.Match) -> str | None:
    hour = int(m.group(1))
    minute = int(m.group(2))
    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if dt <= now:
        dt += timedelta(days=1)
    return dt.isoformat()


def _parse_relative_day(now: datetime, m: re.Match) -> str | None:
    word = m.group(1)
    delta = {"今天": 0, "明天": 1, "后天": 2}.get(word)
    if delta is None:
        return None
    target = now + timedelta(days=delta)
    return target.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
