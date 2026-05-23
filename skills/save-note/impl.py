"""save-note 技能实现 — 保存笔记到收件箱."""

from knowledge_wiki.wiki.paths import save_to_inbox
from knowledge_wiki.wiki.git import commit_and_push
from knowledge_wiki.config import settings

WIKI_ROOT = settings.wiki_root


def execute(context: dict) -> str:
    """保存文本到 raw/收件箱/。

    context 需包含:
        input_text: 文本内容
        user_id: 企业微信用户 ID
        send_md: 发送 markdown 的函数
    """
    text = context.get("input_text", "").strip()
    user_id = context.get("user_id", "")
    send_md = context.get("send_md")

    if not text:
        if send_md:
            send_md(user_id, "请输入要保存的内容。")
        return ""

    filepath = save_to_inbox(text, "text")
    commit_and_push(f"ingest: wecom text {filepath.name}")

    msg = f"已保存到知识库\n\n> 文件：`{filepath.relative_to(WIKI_ROOT)}`\n> 可在 Obsidian 或 MCP 中处理 ingest"

    if send_md:
        send_md(user_id, msg)
    return msg
