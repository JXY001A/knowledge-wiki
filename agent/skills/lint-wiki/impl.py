"""lint-wiki 技能实现 — wiki 健康检查."""


async def execute(context: dict) -> str:
    """执行 wiki 健康检查，返回结构化报告。

    context 可包含:
        send_md: 发送 markdown 消息的函数
        user_id: 企业微信用户 ID
    """
    from knowledge_wiki.mcp.tools.lint import lint_tool

    send_md = context.get("send_md")
    user_id = context.get("user_id", "")

    result = await lint_tool()

    if send_md and user_id:
        # 截取前 3000 字符发送（企业微信有长度限制）
        send_md(user_id, result[:3000])

    return result
