"""管理后台 API — 为仪表盘提供 JSON 数据."""

import json
from datetime import datetime, timedelta
from knowledge_wiki.assistant.db import get_db, init_schema as init_assist
from knowledge_wiki.memory.db import get_db as mem_db, init_schema as init_mem
from knowledge_wiki.memory.models import EpisodicRecord
from knowledge_wiki.assistant.models import Todo, Reminder


def dashboard_data() -> dict:
    """返回仪表盘所需全部数据."""
    return {
        "eval_trend": _eval_trend(),
        "wiki_growth": _wiki_growth(),
        "todos": _todo_stats(),
        "memory_dist": _memory_dist(),
        "gaps": _gaps(),
        "reminders": _reminders(),
        "overview": _overview(),
    }


def _overview() -> dict:
    """概览数字."""
    from knowledge_wiki.wiki.search import list_wiki_pages
    from knowledge_wiki.memory.reader import get_stats as mem_stats
    from knowledge_wiki.eval.scorer import get_eval_stats

    pages = list_wiki_pages()
    mem = mem_stats()
    ev = get_eval_stats()

    ac = get_db()
    init_assist(ac)
    todos_total = ac.execute("SELECT COUNT(*) FROM todos").fetchone()[0] or 0
    todos_pending = ac.execute("SELECT COUNT(*) FROM todos WHERE status='pending'").fetchone()[0] or 0
    ac.close()

    return {
        "wiki_pages": len(pages),
        "concepts": sum(1 for p in pages if p["type"] == "concept"),
        "memories": mem.get("total", 0),
        "eval_avg": ev.get("avg_score", 0),
        "eval_count": ev.get("total", 0),
        "todos_total": todos_total,
        "todos_pending": todos_pending,
    }


def _eval_trend() -> list:
    """最近 30 天评估趋势."""
    conn = mem_db()
    init_mem(conn)
    rows = conn.execute(
        "SELECT date(created_at) as d, AVG(score) as avg, COUNT(*) as cnt "
        "FROM memory_events WHERE score IS NOT NULL AND created_at > date('now', '-30 days') "
        "GROUP BY d ORDER BY d"
    ).fetchall()
    conn.close()
    return [{"date": r[0], "avg": round(r[1], 1), "count": r[2]} for r in rows]


def _wiki_growth() -> list:
    """知识库增长（从 git log 推算）."""
    from knowledge_wiki.config import settings
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", "--format=%ai", "--reverse"],
            cwd=settings.wiki_root, capture_output=True, text=True, timeout=5,
        )
        from collections import Counter
        dates = Counter()
        for line in result.stdout.strip().split("\n"):
            if line:
                dates[line[:10]] += 1

        cumulative = 0
        trend = []
        for d in sorted(dates.keys())[-60:]:
            cumulative += dates[d]
            trend.append({"date": d, "pages": cumulative})

        # Pad to last 60 days
        if len(trend) < 2:
            today = datetime.now().strftime("%Y-%m-%d")
            from knowledge_wiki.wiki.search import list_wiki_pages
            trend = [{"date": today, "pages": len(list_wiki_pages())}]
        return trend
    except Exception:
        from knowledge_wiki.wiki.search import list_wiki_pages
        return [{"date": datetime.now().strftime("%Y-%m-%d"), "pages": len(list_wiki_pages())}]


def _todo_stats() -> dict:
    """待办统计."""
    conn = get_db()
    init_assist(conn)
    total = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0] or 0
    pending = conn.execute("SELECT COUNT(*) FROM todos WHERE status='pending'").fetchone()[0] or 0
    done = conn.execute("SELECT COUNT(*) FROM todos WHERE status='done'").fetchone()[0] or 0
    cancelled = conn.execute("SELECT COUNT(*) FROM todos WHERE status='cancelled'").fetchone()[0] or 0

    overdue = 0
    if pending > 0:
        today = datetime.now().strftime("%Y-%m-%d")
        overdue = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE status='pending' AND deadline < ?", [today]
        ).fetchone()[0] or 0

    # Recent todos
    recent = []
    for r in conn.execute("SELECT * FROM todos ORDER BY created_at DESC LIMIT 5").fetchall():
        t = Todo.from_row(r)
        recent.append({"title": t.title, "status": t.status, "priority": t.priority,
                       "deadline": t.deadline, "created": t.created_at[:10]})

    conn.close()
    return {"total": total, "pending": pending, "done": done, "cancelled": cancelled,
            "overdue": overdue, "recent": recent}


def _memory_dist() -> dict:
    """记忆类型分布."""
    conn = mem_db()
    init_mem(conn)
    labels, counts = [], []
    for r in conn.execute(
        "SELECT event_type, COUNT(*) as cnt FROM memory_events GROUP BY event_type ORDER BY cnt DESC"
    ).fetchall():
        labels.append(r[0])
        counts.append(r[1])
    conn.close()
    return {"labels": labels, "counts": counts}


def _gaps() -> list:
    """Top 知识缺口."""
    try:
        from knowledge_wiki.evolve.auto_ingest import suggest_ingest
        data = suggest_ingest()
        return data.get("gaps", [])[:10]
    except Exception:
        return []


def _reminders() -> list:
    """活跃提醒."""
    conn = get_db()
    init_assist(conn)
    reminders = []
    for r in conn.execute(
        "SELECT * FROM reminders WHERE status='active' AND trigger_at > ? ORDER BY trigger_at LIMIT 10",
        [datetime.now().isoformat()],
    ).fetchall():
        rem = Reminder.from_row(r)
        reminders.append({"content": rem.content, "trigger": rem.trigger_at[:16]})
    conn.close()
    return reminders
