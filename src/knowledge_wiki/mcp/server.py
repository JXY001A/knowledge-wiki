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

    # 注册 Track B 助理工具 — Reminder + Schedule
    from knowledge_wiki.assistant.models import Reminder

    async def remind_set(content: str, trigger_at: str, repeat_rule: str = "") -> str:
        """设置定时提醒."""
        conn = assist_db()
        init_assist(conn)
        r = Reminder(content=content[:200], trigger_at=trigger_at, repeat_rule=repeat_rule or None)
        d = r.to_dict()
        conn.execute(
            f"INSERT INTO reminders ({', '.join(d.keys())}) VALUES ({', '.join('?' for _ in d)})",
            list(d.values()),
        )
        conn.commit()
        conn.close()

        try:
            from knowledge_wiki.assistant.scheduler import add_reminder_job
            add_reminder_job(r.id, content, trigger_at)
        except Exception:
            pass

        return f"⏰ 已设置提醒：{content} | {trigger_at[:16]}"

    async def remind_list(status: str = "active") -> str:
        """列出活跃提醒."""
        conn = assist_db()
        init_assist(conn)
        rows = conn.execute(
            "SELECT * FROM reminders WHERE status=? ORDER BY trigger_at", [status]
        ).fetchall()
        conn.close()
        if not rows:
            return "暂无提醒。"
        reminders = [Reminder.from_row(r) for r in rows]
        lines = [f"## 提醒列表（{len(reminders)} 条）\n"]
        for r in reminders:
            lines.append(f"- ⏰ {r.trigger_at[:16]} | {r.content}")
        return "\n".join(lines)

    async def schedule_today(user_id: str = "") -> str:
        """查看今日日程（待办 + 提醒）."""
        from datetime import datetime, timedelta
        today = datetime.now().date().isoformat()
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()

        conn = assist_db()
        init_assist(conn)

        todos = conn.execute(
            "SELECT * FROM todos WHERE status='pending' ORDER BY "
            "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END LIMIT 10"
        ).fetchall()
        reminders = conn.execute(
            "SELECT * FROM reminders WHERE status='active' AND trigger_at BETWEEN ? AND ? ORDER BY trigger_at",
            [today, tomorrow],
        ).fetchall()
        conn.close()

        lines = ["## 今日日程\n"]
        if todos:
            lines.append("### 待办")
            icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            for i, r in enumerate(todos, 1):
                t = Todo.from_row(r)
                icon = icons.get(t.priority, "⚪")
                lines.append(f"{i}. {icon} {t.title}")
        if reminders:
            lines.append("\n### 提醒")
            for r in reminders:
                rem = Reminder.from_row(r)
                t = rem.trigger_at[11:16] if len(rem.trigger_at) > 11 else ""
                lines.append(f"- ⏰ {t} {rem.content}")
        if not todos and not reminders:
            lines.append("暂无日程安排。")
        return "\n".join(lines)

    mcp.tool()(remind_set)
    mcp.tool()(remind_list)
    mcp.tool()(schedule_today)

    # 注册 Track B 助理工具 — Bookmark
    from knowledge_wiki.assistant.models import Bookmark as BkModel

    async def bookmark_add(url: str, title: str = "", tags: str = "") -> str:
        """保存书签."""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        conn = assist_db()
        init_assist(conn)
        existing = conn.execute("SELECT id FROM bookmarks WHERE url=?", [url]).fetchone()
        if existing:
            conn.close()
            return f"书签已存在：{url[:80]}"
        b = BkModel(url=url, title=title[:80] if title else url[:80], tags=tag_list)
        d = b.to_dict()
        conn.execute(
            f"INSERT INTO bookmarks ({', '.join(d.keys())}) VALUES ({', '.join('?' for _ in d)})",
            list(d.values()),
        )
        conn.commit()
        conn.close()
        return f"📎 已保存书签：{title or url[:60]}"

    async def bookmark_list(read_status: str = "unread", limit: int = 20) -> str:
        """列出书签."""
        conn = assist_db()
        init_assist(conn)
        rows = conn.execute(
            "SELECT * FROM bookmarks WHERE read_status=? ORDER BY created_at DESC LIMIT ?",
            [read_status, limit],
        ).fetchall()
        conn.close()
        if not rows:
            return "暂无书签。"
        bks = [BkModel.from_row(r) for r in rows]
        lines = [f"## 书签（{len(bks)}）\n"]
        for i, b in enumerate(bks, 1):
            lines.append(f"{i}. [{b.title}]({b.url})")
        return "\n".join(lines)

    # 注册 Track B 助理工具 — Habit
    from knowledge_wiki.assistant.models import Habit as HabModel, HabitLog

    async def habit_create(name: str, unit: str = "boolean", target: float = 1.0) -> str:
        """创建习惯."""
        conn = assist_db()
        init_assist(conn)
        h = HabModel(name=name[:20], unit=unit, target=target)
        d = h.to_dict()
        conn.execute(
            f"INSERT INTO habits ({', '.join(d.keys())}) VALUES ({', '.join('?' for _ in d)})",
            list(d.values()),
        )
        conn.commit()
        conn.close()
        return f"✅ 已创建习惯：{name}"

    async def habit_log(habit_name: str, value: float = 1.0, date: str = "") -> str:
        """习惯打卡."""
        from datetime import datetime
        d = date or datetime.now().strftime("%Y-%m-%d")
        conn = assist_db()
        init_assist(conn)
        row = conn.execute("SELECT id FROM habits WHERE name=? AND archived_at IS NULL", [habit_name]).fetchone()
        if not row:
            conn.close()
            return f"习惯「{habit_name}」不存在。先用 habit_create 创建。"
        try:
            hl = HabitLog(habit_id=row["id"], date=d, value=value)
            ld = hl.to_dict()
            conn.execute(
                f"INSERT INTO habit_logs ({', '.join(ld.keys())}) VALUES ({', '.join('?' for _ in ld)})",
                list(ld.values()),
            )
            conn.commit()
            conn.close()
            return f"✅ {habit_name} 打卡成功！"
        except Exception:
            conn.close()
            return f"今日已打卡：{habit_name}"

    async def habit_stats(habit_name: str = "") -> str:
        """查看习惯统计."""
        conn = assist_db()
        init_assist(conn)
        rows = conn.execute(
            "SELECT h.name, COUNT(hl.id) as cnt, MAX(hl.date) as last_date "
            "FROM habits h LEFT JOIN habit_logs hl ON h.id=hl.habit_id "
            "WHERE h.archived_at IS NULL GROUP BY h.id"
        ).fetchall()
        conn.close()
        if not rows:
            return "暂无习惯记录。"
        lines = ["## 习惯统计\n"]
        for r in rows:
            lines.append(f"- {r['name']}: {r['cnt']} 次 | 最后: {r['last_date'] or '无'}")
        return "\n".join(lines)

    async def daily_brief() -> str:
        """生成今日简报."""
        from datetime import datetime, timedelta
        today = datetime.now().date().isoformat()
        conn = assist_db()
        init_assist(conn)
        pending = conn.execute("SELECT COUNT(*) FROM todos WHERE status='pending'").fetchone()[0]
        reminders = conn.execute(
            "SELECT COUNT(*) FROM reminders WHERE status='active' AND trigger_at >= ?", [today]
        ).fetchone()[0]
        notes = conn.execute("SELECT COUNT(*) FROM notes WHERE created_at >= ?", [today]).fetchone()[0]
        conn.close()

        lines = [
            f"## 📋 {datetime.now().strftime('%m月%d日')} 简报\n",
            f"📌 待办：{pending} 项",
            f"⏰ 提醒：{reminders} 个",
            f"📝 笔记：{notes} 条",
        ]
        return "\n".join(lines)

    mcp.tool()(bookmark_add)
    mcp.tool()(bookmark_list)
    mcp.tool()(habit_create)
    mcp.tool()(habit_log)
    mcp.tool()(habit_stats)
    mcp.tool()(daily_brief)

    # 注册 Phase 4 评估工具
    from knowledge_wiki.eval.scorer import evaluate_answer, get_eval_stats

    async def eval_last(question: str, answer: str, wiki_context: str = "") -> str:
        """评估最近一次回答的质量（准确性/完整性/有用性 1-5 分）."""
        result = evaluate_answer(question, answer, wiki_context)
        if not result:
            return "评估失败（API 不可用或未配置）"
        lines = [
            f"## 回答评估",
            f"准确性：{'⭐' * result.accuracy} ({result.accuracy}/5)",
            f"完整性：{'⭐' * result.completeness} ({result.completeness}/5)",
            f"有用性：{'⭐' * result.usefulness} ({result.usefulness}/5)",
            f"综合：{result.stars} ({result.overall}/5)",
        ]
        if result.gaps:
            lines.append(f"\n知识缺口：{', '.join(result.gaps)}")
        if result.improvement:
            lines.append(f"\n建议：{result.improvement}")
        return "\n".join(lines)

    async def eval_stats() -> str:
        """查看评估统计：平均分、分布."""
        stats = get_eval_stats()
        if stats.get("total", 0) == 0:
            return "暂无评估数据。使用 ? 查询后系统会自动评估。"
        lines = [
            f"## 评估统计",
            f"总评估次数：{stats['total']}",
            f"平均评分：{stats['stars']} ({stats['avg_score']}/5)",
        ]
        return "\n".join(lines)

    mcp.tool()(eval_last)
    mcp.tool()(eval_stats)

    # 注册 Phase 5 自进化工具
    from knowledge_wiki.evolve.reporter import weekly_report
    from knowledge_wiki.evolve.gap_detector import detect_gaps, generate_ingest_list

    async def evolve_report() -> str:
        """生成系统自检报告（知识库概览 + 缺口 + Skill 统计 + 建议）."""
        return weekly_report()

    async def evolve_gaps() -> str:
        """检测知识缺口（从低分评估中提取）."""
        gaps = detect_gaps()
        if not gaps:
            return "✅ 暂无低分评估记录，未检测到知识缺口。"
        lines = [f"## 知识缺口（{len(gaps)} 条低分记录）\n"]
        for g in gaps[:10]:
            lines.append(f"- [{g['score']}/5] {g['question']}")
            if g["gaps"]:
                lines.append(f"  缺口：{', '.join(g['gaps'][:3])}")
        return "\n".join(lines)

    async def evolve_ingest_list() -> str:
        """生成待摄取清单（缺口概念 + 未处理资料 + 缺失概念）."""
        data = generate_ingest_list()
        lines = ["## 待摄取清单\n"]

        gaps = data.get("gaps", [])
        if gaps:
            lines.append("### 知识缺口（按频次）")
            for g in gaps[:8]:
                lines.append(f"- {g['topic']}（{g['count']} 次）")

        missing = data.get("missing_concepts", [])
        if missing:
            lines.append("\n### 缺失概念页")
            for m in missing[:5]:
                name = m.get("title", m) if isinstance(m, dict) else m
                lines.append(f"- {name}")

        raw_files = data.get("unprocessed_raw", [])
        if raw_files:
            lines.append(f"\n### 待处理资料（{len(raw_files)} 份）")
            for f in raw_files[:5]:
                lines.append(f"- `{f}`")

        if not gaps and not missing and not raw_files:
            lines.append("✅ 知识库状态良好，暂无待摄取项。")

        return "\n".join(lines)

    mcp.tool()(evolve_report)
    mcp.tool()(evolve_gaps)
    mcp.tool()(evolve_ingest_list)

    # 注册自动摄取工具
    from knowledge_wiki.evolve.auto_ingest import suggest_ingest, auto_ingest_topic, suggest_markdown

    async def evolve_suggest() -> str:
        """搜索知识缺口的补充文章，返回摄取建议."""
        return suggest_markdown()

    async def evolve_auto_ingest(url: str, topic: str = "") -> str:
        """自动摄取指定 URL 的文章（下载 + DeepSeek 分析 + wiki 页面）."""
        return auto_ingest_topic(topic or "手动指定", url)

    mcp.tool()(evolve_suggest)
    mcp.tool()(evolve_auto_ingest)

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
