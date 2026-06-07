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

    # 注册用户画像工具
    from knowledge_wiki.memory.profile import build_profile, write_user_md
    from knowledge_wiki.memory.semantic import concept_coverage_report

    async def profile_view() -> str:
        """查看用户画像（从记忆数据自动生成）."""
        profile = build_profile()
        if profile.get("status") == "empty":
            return "暂无足够的交互数据生成画像。开始使用知识库后自动填充。"
        lines = [
            f"## 用户画像",
            f"总交互：{profile['total']} 次 | 活跃 {profile.get('active_days', 0)} 天",
            f"活跃领域：{list(profile.get('top_domains', {}).keys())[:5]}",
            f"交互类型：{profile.get('by_type', {})}",
        ]
        return "\n".join(lines)

    async def profile_update() -> str:
        """更新 USER.md 用户画像文件."""
        return write_user_md()

    async def concept_coverage() -> str:
        """分析概念覆盖度：缺失概念、领域分布、关联密度."""
        return concept_coverage_report()

    mcp.tool()(profile_view)
    mcp.tool()(profile_update)
    mcp.tool()(concept_coverage)

    # 注册 Track B 助理工具 — Todo
    from knowledge_wiki.assistant.db import get_db as assist_db, init_schema as init_assist
    from knowledge_wiki.assistant.models import Todo, Note

    async def todo_list(status: str = "pending", limit: int = 20) -> str:
        """列出待办事项（按优先级排序）."""
        conn = assist_db()
        init_assist(conn)
        rows = conn.execute(
            "SELECT * FROM todos WHERE status = ? ORDER BY "
            "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
            "created_at DESC LIMIT ?",
            [status, limit],
        ).fetchall()
        conn.close()
        if not rows:
            return "暂无待办。"
        todos = [Todo.from_row(r) for r in rows]
        lines = [f"## 待办列表（{len(todos)} 项）\n"]
        icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        for i, t in enumerate(todos, 1):
            icon = icons.get(t.priority, "⚪")
            line = f"{i}. {icon} {t.title}"
            if t.deadline:
                line += f" | {t.deadline[:10]}"
            lines.append(line)
        return "\n".join(lines)

    async def todo_create(title: str, priority: str = "medium", deadline: str = "", tags: str = "") -> str:
        """创建待办事项."""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        conn = assist_db()
        init_assist(conn)
        t = Todo(title=title[:80], priority=priority, deadline=deadline or None, tags=tag_list)
        d = t.to_dict()
        conn.execute(
            f"INSERT INTO todos ({', '.join(d.keys())}) VALUES ({', '.join('?' for _ in d)})",
            list(d.values()),
        )
        conn.commit()
        conn.close()
        return f"✅ 已创建待办：{title}"

    async def todo_complete(todo_id: str) -> str:
        """完成待办."""
        from datetime import datetime
        conn = assist_db()
        init_assist(conn)
        row = conn.execute("SELECT title FROM todos WHERE id=?", [todo_id]).fetchone()
        if not row:
            conn.close()
            return f"待办 {todo_id} 不存在。"
        conn.execute(
            "UPDATE todos SET status='done', completed_at=?, updated_at=? WHERE id=?",
            [datetime.now().isoformat(), datetime.now().isoformat(), todo_id],
        )
        conn.commit()
        conn.close()
        return f"🎉 已完成：{row['title']}"

    # 注册 Track B 助理工具 — Note
    async def note_create(content: str, tags: str = "") -> str:
        """保存快速笔记."""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        conn = assist_db()
        init_assist(conn)
        n = Note(content=content[:500], tags=tag_list)
        d = n.to_dict()
        conn.execute(
            f"INSERT INTO notes ({', '.join(d.keys())}) VALUES ({', '.join('?' for _ in d)})",
            list(d.values()),
        )
        conn.commit()
        conn.close()
        preview = content[:60] + ("..." if len(content) > 60 else "")
        return f"📝 已保存笔记：{preview}"

    async def note_search(query: str, limit: int = 10) -> str:
        """搜索笔记（FTS5 全文搜索）."""
        conn = assist_db()
        init_assist(conn)
        try:
            rows = conn.execute(
                "SELECT n.* FROM notes n JOIN notes_fts nf ON n.rowid = nf.rowid "
                "WHERE notes_fts MATCH ? ORDER BY rank LIMIT ?",
                [query, limit],
            ).fetchall()
        except Exception:
            rows = conn.execute(
                "SELECT * FROM notes WHERE content LIKE ? LIMIT ?",
                [f"%{query}%", limit],
            ).fetchall()
        conn.close()
        if not rows:
            return f"未找到「{query}」相关笔记。"
        notes = [Note.from_row(r) for r in rows]
        lines = [f"## 笔记搜索：{query}（{len(notes)} 条）\n"]
        for n in notes:
            lines.append(f"- {n.content[:100]}")
        return "\n".join(lines)

    mcp.tool()(todo_list)
    mcp.tool()(todo_create)
    mcp.tool()(todo_complete)
    mcp.tool()(note_create)
    mcp.tool()(note_search)

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
