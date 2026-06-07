"""用户画像 — 从记忆数据中提取用户偏好，自动维护 USER.md.

画像维度：
    - 活跃领域：用户最常查询的知识领域
    - 使用节奏：高峰时段、日均查询数
    - 偏好模型：local/DeepSeek 使用比例
    - 交互风格：短问答 vs 长对话 vs 知识摄取
"""

import json
import logging
from datetime import datetime
from collections import Counter
from pathlib import Path
from knowledge_wiki.config import settings
from knowledge_wiki.memory.db import get_db, init_schema
from knowledge_wiki.wiki.atomic import atomic_write

_log = logging.getLogger(__name__)

USER_MD_PATH = settings.wiki_root / "wiki" / "USER.md"


def build_profile() -> dict:
    """从 memory_events 中提取用户画像数据.

    Returns:
        结构化画像字典
    """
    conn = get_db()
    init_schema(conn)

    try:
        # 总事件数
        total = conn.execute(
            "SELECT COUNT(*) FROM memory_events WHERE user_id != 'system'"
        ).fetchone()[0] or 0

        if total == 0:
            return {"status": "empty", "total": 0, "message": "暂无足够的交互数据来生成画像。"}

        # 按类型统计
        type_rows = conn.execute(
            "SELECT event_type, COUNT(*) as cnt FROM memory_events "
            "WHERE user_id != 'system' GROUP BY event_type ORDER BY cnt DESC"
        ).fetchall()
        type_counts = {r[0]: r[1] for r in type_rows}

        # 按领域统计
        domain_rows = conn.execute(
            "SELECT domain, COUNT(*) as cnt FROM memory_events "
            "WHERE domain != '' AND user_id != 'system' "
            "GROUP BY domain ORDER BY cnt DESC LIMIT 8"
        ).fetchall()
        top_domains = {r[0]: r[1] for r in domain_rows}

        # 时间分布
        time_rows = conn.execute(
            "SELECT created_at FROM memory_events WHERE user_id != 'system' "
            "ORDER BY created_at"
        ).fetchall()
        active_hours = Counter()
        active_dates = Counter()
        for r in time_rows:
            try:
                dt = datetime.fromisoformat(r[0].replace("Z", "+00:00"))
                active_hours[dt.hour] += 1
                active_dates[dt.strftime("%Y-%m-%d")] += 1
            except (ValueError, TypeError):
                pass

        peak_hour = active_hours.most_common(1)[0] if active_hours else (None, 0)
        active_days = len(active_dates)

        # 来源分布
        source_rows = conn.execute(
            "SELECT source, COUNT(*) FROM memory_events "
            "WHERE user_id != 'system' GROUP BY source"
        ).fetchall()
        sources = {r[0]: r[1] for r in source_rows}

        # 评分分布（如有）
        score_rows = conn.execute(
            "SELECT AVG(score) as avg, COUNT(score) as cnt "
            "FROM memory_events WHERE score IS NOT NULL"
        ).fetchone()
        avg_score = round(score_rows[0], 1) if score_rows and score_rows[0] else None

        return {
            "status": "ok",
            "total": total,
            "by_type": type_counts,
            "top_domains": top_domains,
            "peak_hour": list(peak_hour),
            "active_days": active_days,
            "sources": sources,
            "avg_score": avg_score,
        }

    except Exception as e:
        _log.warning("构建画像失败: %s", e)
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def generate_user_md(profile: dict | None = None) -> str:
    """生成 USER.md 的 markdown 内容.

    Args:
        profile: 画像数据，None 则实时构建

    Returns:
        markdown 文本
    """
    if profile is None:
        profile = build_profile()

    if profile.get("status") == "empty":
        return _empty_user_md()

    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        "---",
        "title: USER",
        "type: entity",
        "tags: [用户画像, 系统]",
        f"created: {today}",
        f"updated: {today}",
        "sources: []",
        "confidence: medium",
        "---",
        "",
        "# 用户画像",
        "",
        "> 由 AI 自进化知识系统自动生成和维护。反映用户在知识库中的长期行为模式。",
        "",
        "## 行为概览",
        "",
        f"| 指标 | 值 |",
        f"|------|----|",
        f"| 总交互次数 | {profile['total']} |",
        f"| 活跃天数 | {profile['active_days']} |",
    ]

    peak_hour = profile.get("peak_hour")
    if peak_hour and peak_hour[1] > 0:
        lines.append(f"| 高峰时段 | {peak_hour[0]}:00（{peak_hour[1]} 次） |")

    avg_score = profile.get("avg_score")
    if avg_score:
        lines.append(f"| 平均评分 | ⭐ {avg_score}/5 |")

    # 交互类型
    by_type = profile.get("by_type", {})
    if by_type:
        lines.append("")
        lines.append("## 交互类型分布")
        lines.append("")
        lines.append("| 类型 | 次数 |")
        lines.append("|------|------|")
        type_labels = {"query": "🔍 知识查询", "ingest": "📥 知识摄取", "lint": "🔬 健康检查",
                       "note": "📝 笔记", "synthesis": "📊 综合分析"}
        for t, c in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            label = type_labels.get(t, t)
            lines.append(f"| {label} | {c} |")

    # 活跃领域
    top_domains = profile.get("top_domains", {})
    if top_domains:
        lines.append("")
        lines.append("## 活跃知识领域")
        lines.append("")
        lines.append("| 领域 | 查询次数 |")
        lines.append("|------|---------|")
        for d, c in sorted(top_domains.items(), key=lambda x: x[1], reverse=True)[:8]:
            lines.append(f"| {d} | {c} |")

    # 交互来源
    sources = profile.get("sources", {})
    if sources:
        lines.append("")
        lines.append("## 交互来源")
        lines.append("")
        lines.append("| 来源 | 次数 |")
        lines.append("|------|------|")
        source_labels = {"wecom": "企业微信", "mcp": "MCP 工具", "cli": "CLI", "auto": "系统自动"}
        for s, c in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            label = source_labels.get(s, s)
            lines.append(f"| {label} | {c} |")

    lines.append("")
    lines.append("## 相关")
    lines.append("")
    lines.append("- [[知识库概览]]")
    lines.append("- [[Wiki 目录]]")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*本页面由 `memory/profile.py` 自动生成，每次 lint 时更新。*")

    return "\n".join(lines)


def write_user_md() -> str:
    """生成并写入 USER.md。返回更新摘要."""
    profile = build_profile()
    content = generate_user_md(profile)
    atomic_write(USER_MD_PATH, content)
    return f"USER.md 已更新（{profile['total']} 次交互）"


def _empty_user_md() -> str:
    """空画像时的占位 USER.md."""
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""---
title: USER
type: entity
tags: [用户画像, 系统]
created: {today}
updated: {today}
sources: []
confidence: low
---

# 用户画像

> 暂无足够的交互数据。开始使用知识库（查询、摄取）后，本页面将自动填充行为分析。

## 相关

- [[知识库概览]]
- [[Wiki 目录]]
"""
