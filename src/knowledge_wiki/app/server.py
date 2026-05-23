"""MCP Server 入口 — FastMCP 实例 + 工具注册."""


def run_server(host: str | None = None, port: int | None = None):
    """启动 MCP Server（host/port 由 config/settings 确定）."""
    from knowledge_wiki.mcp.server import create_server

    mcp = create_server()
    mcp.run(transport="streamable-http")
