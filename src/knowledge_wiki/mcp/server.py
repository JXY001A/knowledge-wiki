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

    # 注册 Phase 3 记忆工具
    from knowledge_wiki.memory.reader import recent_events, search_memory, get_stats as memory_stats
    from knowledge_wiki.memory.reader import recent_context

    async def memory_recent(limit: int = 10, event_type: str = "all") -> str:
        """查询最近 N 条记忆事件.

        Args:
            limit: 返回条数（默认 10）
            event_type: 筛选类型：all/query/ingest/lint/system
        """
        et = event_type if event_type != "all" else None
        events = recent_events(limit=limit, event_type=et)
        if not events:
            return "暂无记忆记录。"
        lines = [f"## 最近记忆（{len(events)} 条）\n"]
        for e in events:
            icon = {"query": "🔍", "ingest": "📥", "lint": "🔬", "system": "⚙️", "synthesis": "📝"}.get(e.event_type, "•")
            lines.append(f"- {icon} [{e._date_str()[:10]}] {e.summary}")
        return "\n".join(lines)

    async def memory_search(query: str, limit: int = 10) -> str:
        """全文搜索记忆事件.

        Args:
            query: 搜索关键词
            limit: 返回条数（默认 10）
        """
        results = search_memory(query, limit=limit)
        if not results:
            return f"未找到与「{query}」相关的记忆。"
        lines = [f"## 记忆搜索结果：{query}（{len(results)} 条）\n"]
        for e in results:
            lines.append(f"### [{e._date_str()[:10]}] {e.summary}")
            if e.details:
                lines.append(f"{e.details[:300]}")
            lines.append("---")
        return "\n".join(lines)

    async def memory_stats_tool() -> str:
        """获取记忆系统统计摘要."""
        stats = memory_stats()
        if "error" in stats:
            return f"记忆系统不可用：{stats['error']}"
        lines = [
            f"## 记忆统计",
            f"总计：{stats['total']} 条",
            f"按类型：{stats.get('by_type', {})}",
            f"最后记录：{stats.get('last_event_summary', '无')}",
        ]
        return "\n".join(lines)

    async def memory_context(limit: int = 5) -> str:
        """生成最近记忆的上下文文本（供 Agent system prompt 注入）.

        Args:
            limit: 包含最近 N 条
        """
        ctx = recent_context(limit)
        return ctx if ctx else "暂无记忆上下文。"

    mcp.tool()(memory_recent)
    mcp.tool()(memory_search)
    mcp.tool()(memory_stats_tool)
    mcp.tool()(memory_context)

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
