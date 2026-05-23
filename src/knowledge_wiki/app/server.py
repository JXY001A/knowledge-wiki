"""MCP Server 入口 — FastMCP 实例 + 工具注册."""


def run_server(host: str | None = None, port: int | None = None):
    """启动 MCP Server."""
    from knowledge_wiki.config import settings
    from knowledge_wiki.mcp.server import create_server

    host = host or settings.mcp_host
    port = port or settings.mcp_port

    mcp = create_server()
    mcp.run(transport="streamable-http", host=host, port=port)
