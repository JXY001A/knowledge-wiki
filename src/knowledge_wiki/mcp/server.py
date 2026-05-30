"""MCP Server — FastMCP 实例创建与工具注册."""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from knowledge_wiki.config import settings


def create_server() -> FastMCP:
    """创建并配置 FastMCP 实例，注册所有工具."""
    mcp = FastMCP(
        "wiki-server",
        host=settings.mcp_host,
        port=settings.mcp_port,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", "8.133.175.201:*"],
            allowed_origins=["*"],
        ),
    )

    # 注册 Phase 1 工具
    from knowledge_wiki.mcp.tools.search import search_tool
    from knowledge_wiki.mcp.tools.query import query_tool
    from knowledge_wiki.mcp.tools.lint import lint_tool
    from knowledge_wiki.mcp.tools.ingest import ingest_tool

    mcp.tool()(search_tool)
    mcp.tool(name="query")(query_tool)  # 注册为 "query"（兼容旧客户端）
    mcp.tool(name="query_tool")(query_tool)  # 别名
    mcp.tool()(lint_tool)
    mcp.tool()(ingest_tool)

    # 注册 Phase 2 技能工具
    from knowledge_wiki.skill.registry import get_skills_summary
    from knowledge_wiki.skill.planner import execute_skill

    async def skill_list() -> str:
        """列出所有可用技能及其描述。使用此工具了解系统支持的能力."""
        return get_skills_summary()

    async def skill_execute(name: str, intent: str = "") -> str:
        """执行指定技能。

        Args:
            name: 技能名称（使用 skill-list 查看可用技能）
            intent: 用户意图描述（可选，用于传递上下文）
        """
        return execute_skill(name, intent)

    mcp.tool()(skill_list)
    mcp.tool()(skill_execute)

    return mcp
