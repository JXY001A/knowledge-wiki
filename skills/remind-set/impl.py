"""remind-set 技能实现 — 定时提醒设置."""

import re
from datetime import datetime, timedelta


def execute(context: dict) -> str:
    """解析用户意图，设置定时提醒并注册到调度器.

    context 需包含:
        input_text: 用户输入
        user_id: 企业微信用户 ID
        send_md: 发送 markdown 的函数
    """
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Reminder

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    text = context.get("input_text", "").strip()

    # 去除触发词
    for kw in ["提醒", "闹钟", "定时", "叫我", "记得", "别忘"]:
        if kw in text[:6]:
            text = text.replace(kw, "", 1).strip()
            break

    if not text:
        msg = "请指定提醒内容和时间。\n\n用法：提醒 <内容> <时间>"
        if send_md:
            send_md(user_id, msg)
        return msg

    # 解析时间和内容
    trigger_at, content = _parse_reminder(text)
    if not trigger_at:
        msg = "无法识别时间，请用以下格式：\n- 提醒 下午3点 code review\n- 提醒 明天9:00 站会"
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

    # 注册到调度器
    try:
        from knowledge_wiki.assistant.scheduler import add_reminder_job
        add_reminder_job(r.id, content, trigger_at, user_id=user_id)
    except Exception:
        pass  # 调度器未启动时静默跳过

    # 格式化回复
    try:
        dt = datetime.fromisoformat(trigger_at)
        time_str = dt.strftime("%m月%d日 %H:%M")
    except (ValueError, TypeError):
        time_str = trigger_at[:16]

    msg = f"⏰ 已设置提醒\n\n**{content}**\n时间：{time_str}"

    if send_md:
        send_md(user_id, msg[:3000])
    return msg


def _parse_reminder(text: str) -> tuple[str | None, str]:
    """从自然语言中解析时间和内容.

    Returns:
        (trigger_at_iso, content) 或 (None, raw_text) 如果解析失败
    """
    now = datetime.now()
    today = now.date()

    # 尝试提取时间模式
    time_patterns = [
        # "下午3点" → 15:00
        (r"(上午|下午|晚上|中午)?(\d{1,2})[点:：](\d{0,2})?", _parse_cn_time),
        # "3pm" / "15:00"
        (r"(\d{1,2}):(\d{2})", _parse_24h_time),
        # "明天" / "后天"
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

    # 清理内容
    content = text
    if trigger_at:
        # 移除时间相关文本
        content = re.sub(r"(上午|下午|晚上|中午)?\d{1,2}[点:：]\d{0,2}分?", "", content)
        content = re.sub(r"\d{1,2}:\d{2}", "", content)
        content = re.sub(r"明天|后天|今天", "", content)
        content = content.strip()

    return trigger_at, content if content else text


def _parse_cn_time(now: datetime, m: re.Match) -> str | None:
    """解析中文时间."""
    period = m.group(1) or ""
    hour = int(m.group(2))
    minute = int(m.group(3)) if m.group(3) else 0

    # 调整上下午
    if "下午" in period and hour < 12:
        hour += 12
    elif "晚上" in period:
        if hour < 12:
            hour += 12
    elif "上午" in period and hour == 12:
        hour = 0
    elif "中午" in period and hour < 12:
        hour += 12

    if hour > 23:
        hour = 23
    if minute > 59:
        minute = 59

    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    # 如果时间已过，设为明天
    if dt <= now:
        dt += timedelta(days=1)

    return dt.isoformat()


def _parse_24h_time(now: datetime, m: re.Match) -> str | None:
    """解析 24 小时制时间."""
    hour = int(m.group(1))
    minute = int(m.group(2))
    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if dt <= now:
        dt += timedelta(days=1)
    return dt.isoformat()


def _parse_relative_day(now: datetime, m: re.Match) -> str | None:
    """解析相对日期."""
    word = m.group(1)
    delta = {"今天": 0, "明天": 1, "后天": 2}.get(word)
    if delta is None:
        return None
    target = now + timedelta(days=delta)
    return target.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
