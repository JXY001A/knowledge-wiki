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
        "skills": _skills(),
        "wiki_pages": _wiki_page_list(),
        "query_log": _query_log(),
        "server_status": _server_status(),
        # 质量面板新数据
        "quality": _quality_panel(),
    }


def _server_status() -> dict:
    """DevMechin 服务器状态."""
    import subprocess, os

    services = {}
    # 检查 systemd 服务
    for name in ["wiki-mcp", "wecom-webhook", "wiki-scheduler"]:
        try:
            r = subprocess.run(
                ["systemctl", "--user", "is-active", name],
                capture_output=True, text=True, timeout=5,
            )
            services[name] = r.stdout.strip() == "active"
        except Exception:
            services[name] = False

    # Ollama
    try:
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                           "http://localhost:11434/api/tags"], capture_output=True, text=True, timeout=5)
        services["ollama"] = r.stdout.strip() == "200"
    except Exception:
        services["ollama"] = False

    # FRP
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", "frpc"],
                          capture_output=True, text=True, timeout=5)
        services["frpc"] = r.stdout.strip() == "active"
    except Exception:
        services["frpc"] = False

    # GPU
    gpu = {}
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                           "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            parts = r.stdout.strip().split(",")
            if len(parts) >= 5:
                gpu = {"name": parts[0].strip(), "util": parts[1].strip(),
                       "mem_used": parts[2].strip(), "mem_total": parts[3].strip(),
                       "temp": parts[4].strip()}
    except Exception:
        pass

    # System
    system = {}
    try:
        r = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        system["uptime"] = r.stdout.strip().replace("up ", "")
    except Exception:
        system["uptime"] = "?"

    try:
        r = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if "Mem:" in line or "内存" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p in ("Mem:", "内存："):
                        if len(parts) > i+2:
                            system["mem_total"] = parts[i+1]
                            system["mem_used"] = parts[i+2]
                        break
                if "mem_total" not in system:
                    # Fallback: third column is used, second is total
                    if len(parts) >= 3:
                        system["mem_total"] = parts[1]
                        system["mem_used"] = parts[2]
                break
    except Exception:
        pass

    try:
        r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 5:
                system["disk_used"] = parts[2]
                system["disk_total"] = parts[1]
                system["disk_pct"] = parts[4]
    except Exception:
        pass

    return {"services": services, "gpu": gpu, "system": system}



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
        dl = (t.deadline or "")[:10] if t.deadline else ""
        created = str(t.created_at)[:16] if t.created_at else ""
        recent.append({"title": t.title, "status": t.status, "priority": t.priority,
                       "deadline": dl, "created": created})

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


def _skills() -> list:
    """已注册 Skill 列表及统计."""
    from knowledge_wiki.skill.registry import list_skills
    from knowledge_wiki.memory.db import get_db as memdb, init_schema as mem_init
    from knowledge_wiki.assistant.db import get_db as adb, init_schema as ainit

    skills = list_skills()

    # Skill 名称到 event_type 的映射
    type_map = {
        "query-knowledge": "query",
        "ingest-article": "ingest",
        "lint-wiki": "lint",
        "auto-ingest": "ingest",
    }

    # 从 memory_events 获取执行次数
    mconn = memdb()
    mem_init(mconn)
    type_counts = {}
    for r in mconn.execute(
        "SELECT event_type, COUNT(*) as cnt FROM memory_events GROUP BY event_type"
    ).fetchall():
        type_counts[r[0]] = r[1]
    mconn.close()

    # 从 assistant db 获取待办统计
    aconn = adb()
    ainit(aconn)
    todo_count = aconn.execute("SELECT COUNT(*) FROM todos").fetchone()[0] or 0
    aconn.close()

    result = []
    for s in skills:
        evt = type_map.get(s.name, s.name.replace("-", "_"))
        count = type_counts.get(evt, 0) if evt in type_counts else 0
        # todo-manage 从 todos 表统计
        if s.name == "todo-manage":
            count = todo_count
        result.append({
            "name": s.name,
            "description": s.description[:50],
            "tier": s.tier,
            "model": s.model,
            "triggers": s.triggers[:5],
            "count": count,
        })

    return sorted(result, key=lambda s: -s["count"])


def _wiki_page_list() -> list:
    """知识库页面列表（按目录分组）."""
    from knowledge_wiki.wiki.search import list_wiki_pages

    pages = list_wiki_pages()
    by_dir = {}
    for p in pages:
        path = p["path"]
        parts = path.split("/")
        if len(parts) >= 3:
            directory = parts[1]  # wiki/<directory>/page.md
        else:
            directory = "根目录"
        if directory not in by_dir:
            by_dir[directory] = []
        upd = p.get("updated", "")
        if hasattr(upd, "strftime"):
            upd = upd.strftime("%Y-%m-%d")
        upd_str = str(upd)[:10] if upd else ""
        by_dir[directory].append({
            "title": p["title"],
            "type": p["type"],
            "tags": p["tags"][:5] if isinstance(p.get("tags"), list) else [],
            "updated": upd_str,
            "confidence": p.get("confidence", ""),
        })

    # 按目录分组返回
    result = []
    for d in sorted(by_dir.keys()):
        result.append({
            "directory": d,
            "count": len(by_dir[d]),
            "pages": sorted(by_dir[d], key=lambda p: p["title"]),
        })
    return result


def _query_log() -> list:
    """每日询问日志（最近 50 条 query/eval 记录）."""
    from knowledge_wiki.memory.db import get_db as memdb, init_schema as mem_init

    conn = memdb()
    mem_init(conn)
    rows = conn.execute(
        "SELECT * FROM memory_events WHERE event_type IN ('query', 'eval') "
        "ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()

    icons = {"query": "🔍", "eval": "📊", "ingest": "📥", "lint": "🔬"}
    log = []
    for r in rows:
        log.append({
            "type": r["event_type"],
            "icon": icons.get(r["event_type"], "•"),
            "summary": r["summary"][:80],
            "score": r["score"],
            "created": str(r["created_at"])[:16] if r["created_at"] else "",
        })

    return log


def _quality_panel() -> dict:
    """知识库质量面板数据 — 评估均分趋势、低分领域、缺口状态、自动摄取统计."""
    from knowledge_wiki.eval.scorer import get_eval_stats
    from knowledge_wiki.evolve.gap_detector import get_recurring_gaps, generate_ingest_list

    # 评估统计
    eval_stats = get_eval_stats()

    # 低分领域排行（从详情中提取）
    low_score_domains = _low_score_domains()

    # 知识缺口
    recurring_gaps = get_recurring_gaps(min_occurrences=2, days=30)
    ingest_list = generate_ingest_list()

    # 自动摄取统计
    auto_ingest_stats = _auto_ingest_stats()

    # 关联建议（最多返回 5 条，避免 Dashboard 过重）
    relation_suggestions = []
    try:
        from knowledge_wiki.wiki.retrieval.deep_process import discover_relations
        relations = discover_relations(min_similarity=0.7, max_suggestions=5)
        relation_suggestions = [
            {"page1": r.page1, "page2": r.page2,
             "similarity": r.similarity, "action": r.suggested_action}
            for r in relations
        ]
    except Exception:
        pass

    return {
        "eval_avg": eval_stats.get("avg_score", 0),
        "eval_total": eval_stats.get("total", 0),
        "eval_stars": eval_stats.get("stars", "暂无"),
        "low_score_domains": low_score_domains[:5],
        "recurring_gaps": [
            {"topic": g["topic"], "count": g["count"], "last_seen": g["last_seen"]}
            for g in recurring_gaps[:10]
        ],
        "unprocessed_raw": ingest_list.get("unprocessed_raw", [])[:5],
        "missing_concepts": [
            c if isinstance(c, str) else c.get("title", str(c))
            for c in ingest_list.get("missing_concepts", [])[:5]
        ],
        "auto_ingest": auto_ingest_stats,
        "relation_suggestions": relation_suggestions,
    }


def _low_score_domains() -> list[dict]:
    """从评估记录中提取低分领域排行."""
    try:
        from knowledge_wiki.memory.db import get_db, init_schema
        conn = get_db()
        init_schema(conn)
        rows = conn.execute(
            "SELECT details, score FROM memory_events "
            "WHERE score IS NOT NULL AND score <= 3 "
            "ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        conn.close()

        from collections import Counter
        domain_counter = Counter()
        for r in rows:
            details = r["details"] or ""
            # 尝试从 details 的 JSON 中提取 gaps
            import json, re
            try:
                m = re.search(r"\{[^{}]*\"gaps\"[^{}]*\}", details, re.DOTALL)
                if m:
                    data = json.loads(m.group(0))
                    for gap in data.get("gaps", []):
                        domain_counter[gap] += 1
            except Exception:
                pass

        return [{"domain": k, "count": v} for k, v in domain_counter.most_common(10)]
    except Exception:
        return []


def _auto_ingest_stats() -> dict:
    """自动摄取统计."""
    try:
        from knowledge_wiki.evolve.auto_ingest import (
            _load_auto_ingest_log,
            MAX_AUTO_INGEST_PER_WEEK,
        )
        log = _load_auto_ingest_log()
        imported = datetime.now().isoformat()
        return {
            "week_count": log.get("count", 0),
            "week_limit": MAX_AUTO_INGEST_PER_WEEK,
            "ingested": log.get("ingested", [])[-5:],  # 最近 5 条
            "week_start": log.get("week_start", ""),
        }
    except Exception:
        return {"week_count": 0, "week_limit": 5, "ingested": [], "week_start": ""}
