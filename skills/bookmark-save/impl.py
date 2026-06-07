"""bookmark-save 技能实现 — URL 书签保存."""

import re


def execute(context: dict) -> str:
    """保存 URL 书签，自动提取标题和标签."""
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Bookmark

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    text = context.get("input_text", "").strip()

    # 去除触发词
    for kw in ["书签", "收藏", "稍后读", "bookmark", "标记"]:
        if kw in text[:6]:
            text = text.replace(kw, "", 1).strip()
            break

    # 提取 URL
    url_match = re.search(r"https?://[^\s]+", text)
    if not url_match:
        msg = "未找到 URL。用法：书签 https://example.com 描述 #标签"
        if send_md:
            send_md(user_id, msg)
        return msg

    url = url_match.group(0)
    desc = text.replace(url, "").strip()

    # 提取标签
    tags = re.findall(r"[#＃]([\w一-鿿]+)", desc)

    # 尝试获取网页标题（快速失败，不阻塞）
    title = desc[:80] if desc else url[:80]
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")[:2000]
            t = re.search(r"<title>(.+?)</title>", html, re.IGNORECASE)
            if t:
                title = t.group(1).strip()[:80]
    except Exception:
        pass

    conn = get_db()
    init_schema(conn)

    # 去重检查
    existing = conn.execute("SELECT id FROM bookmarks WHERE url=?", [url]).fetchone()
    if existing:
        conn.close()
        msg = f"📎 书签已存在：**{title}**"
        if send_md:
            send_md(user_id, msg)
        return msg

    b = Bookmark(url=url, title=title, description=desc[:200], tags=tags)
    d = b.to_dict()
    cols = ", ".join(d.keys())
    ph = ", ".join("?" for _ in d)
    conn.execute(f"INSERT INTO bookmarks ({cols}) VALUES ({ph})", list(d.values()))
    conn.commit()
    conn.close()

    msg = f"📎 已保存书签：**{title}**"
    if tags:
        msg += f"\n标签：{', '.join(tags)}"
    msg += f"\n\n{url[:100]}"

    if send_md:
        send_md(user_id, msg[:3000])
    return msg
