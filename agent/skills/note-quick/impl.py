"""note-quick 技能实现 — 快速笔记保存."""

import re


def execute(context: dict) -> str:
    """保存快速笔记到助理数据库.

    context 需包含:
        input_text: 笔记内容
        user_id: 用户 ID
        send_md: 回复回调（可选）
    """
    from knowledge_wiki.assistant.db import get_db, init_schema
    from knowledge_wiki.assistant.models import Note

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    text = context.get("input_text", "").strip()

    # 去除触发词
    for kw in ["笔记", "记一下", "备忘", "备注", "闪念", "便签"]:
        if text.lower().startswith(kw.lower()):
            text = text[len(kw):].strip()
            break

    if not text:
        msg = "请输入笔记内容。\n\n用法：笔记 <内容> #标签（可选）"
        if send_md:
            send_md(user_id, msg)
        return msg

    # 提取标签（#xxx 和 @xxx）
    tags = re.findall(r"[#＃]([\w一-鿿]+)", text)
    # 清理正文中的标签（保留正文可读性）
    clean = re.sub(r"[#＃][\w一-鿿]+", "", text).strip()

    # 自动提取标签（如果用户没手动打标签）
    if not tags:
        tags = _auto_tag(clean)

    # 提取 wikilink 关联
    wiki_links = re.findall(r"\[\[([^\]]+)\]\]", clean)
    related = wiki_links[0] if wiki_links else ""

    conn = get_db()
    init_schema(conn)

    note = Note(
        content=clean[:500],
        tags=tags[:5],
        related_page=related,
        source="wecom" if user_id else "cli",
    )
    d = note.to_dict()
    cols = ", ".join(d.keys())
    ph = ", ".join("?" for _ in d)
    conn.execute(f"INSERT INTO notes ({cols}) VALUES ({ph})", list(d.values()))
    conn.commit()
    conn.close()

    # 构建回复
    preview = clean[:60] + ("..." if len(clean) > 60 else "")
    msg = f"📝 已保存笔记"
    if tags:
        msg += f"\n标签：{', '.join(tags)}"
    msg += f"\n\n> {preview}"

    if send_md:
        send_md(user_id, msg[:3000])
    return msg


def _auto_tag(text: str) -> list[str]:
    """根据关键词自动提取标签."""
    tag_map = {
        "部署": "运维", "deploy": "运维", "docker": "运维",
        "python": "开发", "代码": "开发", "git": "开发",
        "企微": "工具", "wecom": "工具", "bot": "工具",
        "MCP": "MCP", "mcp": "MCP",
        "Agent": "Agent", "agent": "Agent",
        "待办": "工作", "todo": "工作",
        "DevMechin": "基础设施", "服务器": "基础设施",
        "AI": "AI", "模型": "AI", "LLM": "AI",
    }
    found = []
    for kw, tag in tag_map.items():
        if kw.lower() in text.lower() and tag not in found:
            found.append(tag)
    return found[:3]
