"""自检报告 — 周度系统健康报告 + Skill 效果追踪.

生成内容：
    1. 知识库概览（页面数、概念数、评估均分）
    2. 知识缺口（高频缺失概念）
    3. 待处理资料（raw/ 未 ingest）
    4. Skill 执行统计
    5. 建议行动
"""

from datetime import datetime
from collections import Counter
from knowledge_wiki.memory.db import get_db, init_schema


def weekly_report() -> str:
    """生成周度自检报告（markdown）.

    Returns:
        markdown 格式的完整报告
    """
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"# 🏥 系统自检报告",
        f"",
        f"生成时间：{today}",
        f"",
    ]

    # 1. 知识库概览
    lines.append("## 知识库概览")
    lines.extend(_kb_overview())
    lines.append("")

    # 2. 记忆与评估
    lines.append("## 记忆与评估")
    lines.extend(_memory_overview())
    lines.append("")

    # 3. 知识缺口
    lines.append("## 知识缺口")
    lines.extend(_gap_section())
    lines.append("")

    # 4. Skill 统计
    lines.append("## Skill 执行统计")
    lines.extend(_skill_section())
    lines.append("")

    # 5. 建议行动
    lines.append("## 建议行动")
    lines.extend(_action_section())
    lines.append("")

    lines.append("---")
    lines.append(f"*本报告由 evolve/reporter.py 自动生成*")

    return "\n".join(lines)


def skill_stats() -> list[dict]:
    """统计各 Skill 的执行情况.

    Returns:
        [{"skill": "todo-manage", "count": N, "last_used": "..."}]
    """
    conn = get_db()
    init_schema(conn)

    # 从 memory_events 按 event_type 统计（query/ingest/lint/system 对应技能）
    type_skill_map = {
        "query": "query-knowledge",
        "ingest": "ingest-article",
        "lint": "lint-wiki",
    }

    stats = []
    for event_type, skill_name in type_skill_map.items():
        row = conn.execute(
            "SELECT COUNT(*), MAX(created_at) FROM memory_events WHERE event_type = ?",
            [event_type],
        ).fetchone()
        stats.append({
            "skill": skill_name,
            "count": row[0] or 0,
            "last_used": str(row[1])[:10] if row[1] else "从未",
        })

    # 待办统计
    try:
        from knowledge_wiki.assistant.db import get_db as adb, init_schema as ainit
        ac = adb()
        ainit(ac)
        todo_count = ac.execute("SELECT COUNT(*) FROM todos").fetchone()[0] or 0
        todo_last = ac.execute("SELECT MAX(created_at) FROM todos").fetchone()[0]
        ac.close()
        stats.append({"skill": "todo-manage", "count": todo_count, "last_used": str(todo_last)[:10] if todo_last else "从未"})
    except Exception:
        stats.append({"skill": "todo-manage", "count": 0, "last_used": "未知"})

    conn.close()
    return stats


def _kb_overview() -> list[str]:
    """知识库概览."""
    from knowledge_wiki.wiki.search import list_wiki_pages
    from knowledge_wiki.eval.scorer import get_eval_stats

    pages = list_wiki_pages()
    eval_s = get_eval_stats()
    concepts = [p for p in pages if p["type"] == "concept"]
    sources = [p for p in pages if p["type"] == "source"]

    return [
        f"| 指标 | 值 |",
        f"|------|----|",
        f"| wiki 页面 | {len(pages)} |",
        f"| 概念页 | {len(concepts)} |",
        f"| 资料摘要 | {len(sources)} |",
        f"| 评估均分 | {eval_s['stars']} ({eval_s['avg_score']}/5) |" if eval_s.get("total", 0) > 0 else f"| 评估 | 暂无 |",
        f"| 评估次数 | {eval_s.get('total', 0)} |",
    ]


def _memory_overview() -> list[str]:
    """记忆与评估概况."""
    from knowledge_wiki.memory.reader import get_stats

    mem = get_stats()
    if mem.get("total", 0) == 0:
        return ["暂无记忆记录。"]

    lines = [
        f"| 指标 | 值 |",
        f"|------|----|",
        f"| 总记忆记录 | {mem.get('total', 0)} |",
    ]
    by_type = mem.get("by_type", {})
    for t, c in by_type.items():
        lines.append(f"| {t} | {c} |")
    if mem.get("last_event_summary"):
        lines.append(f"| 最近事件 | {mem['last_event_summary'][:60]} |")

    return lines


def _gap_section() -> list[str]:
    """知识缺口分析."""
    from knowledge_wiki.evolve.gap_detector import generate_ingest_list

    ingest = generate_ingest_list()
    gaps = ingest.get("gaps", [])
    unprocessed = ingest.get("unprocessed_raw", [])
    missing = ingest.get("missing_concepts", [])

    lines = []

    if gaps:
        lines.append("### 高频知识缺口")
        for g in gaps[:8]:
            lines.append(f"- **{g['topic']}**（{g['count']} 次）")

    if missing:
        lines.append("\n### 缺少独立页面的概念")
        for m in missing[:5]:
            lines.append(f"- {m.get('title', m) if isinstance(m, dict) else m}")

    if unprocessed:
        lines.append(f"\n### 待摄取资料（{len(unprocessed)} 份）")
        for u in unprocessed[:5]:
            lines.append(f"- `{u}`")

    if not gaps and not missing and not unprocessed:
        lines.append("✅ 未检测到明显的知识缺口。")

    return lines


def _skill_section() -> list[str]:
    """Skill 执行统计."""
    stats = skill_stats()
    if not stats:
        return ["暂无 Skill 执行记录。"]

    lines = [
        f"| 技能 | 执行次数 | 最后使用 |",
        f"|------|---------|---------|",
    ]
    for s in stats:
        lines.append(f"| {s['skill']} | {s['count']} | {s['last_used']} |")

    return lines


def _action_section() -> list[str]:
    """建议行动."""
    from knowledge_wiki.evolve.gap_detector import generate_ingest_list

    ingest = generate_ingest_list()
    suggestions = []

    if ingest.get("unprocessed_raw"):
        suggestions.append(f"📥 处理 {len(ingest['unprocessed_raw'])} 份待摄取资料：`ingest`")

    if ingest.get("gaps"):
        top = ingest["gaps"][0]
        suggestions.append(f"🔍 优先补全「{top['topic']}」相关知识（{top['count']} 次查询未找到满意答案）")

    if ingest.get("missing_concepts"):
        name = ingest["missing_concepts"][0]
        n = name.get("title", name) if isinstance(name, dict) else name
        suggestions.append(f"📝 创建缺失的概念页面：{n}")

    from knowledge_wiki.eval.scorer import get_eval_stats
    eval_s = get_eval_stats()
    if eval_s.get("total", 0) > 0 and eval_s.get("avg_score", 5) < 4:
        suggestions.append(f"📊 回答均分 {eval_s['avg_score']}/5，建议持续摄入高质量资料")

    if not suggestions:
        suggestions.append("✅ 系统运行良好，暂无紧急建议。")

    return [f"{i+1}. {s}" for i, s in enumerate(suggestions)]
