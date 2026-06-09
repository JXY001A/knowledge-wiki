"""记忆读取器 — 结构化查询 API.

支持按时间、类型、标签、评分检索记忆记录，以及 FTS5 全文搜索。
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any
from knowledge_wiki.config import settings
from knowledge_wiki.memory.models import EpisodicRecord
from knowledge_wiki.memory.db import get_db, init_schema
from knowledge_wiki.wiki.frontmatter import strip_frontmatter

_log = logging.getLogger(__name__)

OPERATION_LOG = settings.wiki_root / "wiki" / "操作日志.md"


def _ensure_db() -> sqlite3.Connection | None:
    """获取数据库连接，初始化 schema。失败返回 None."""
    try:
        conn = get_db()
        init_schema(conn)
        return conn
    except sqlite3.Error as e:
        _log.warning("memory db 不可用: %s", e)
        return None


# ---- 查询 API ----

def recent_events(
    limit: int = 10,
    event_type: str | None = None,
    user_id: str | None = None,
) -> list[EpisodicRecord]:
    """获取最近 N 条记忆事件.

    Args:
        limit: 返回条数
        event_type: 可选筛选类型（'query'/'ingest'/'lint'/'system'）
        user_id: 可选筛选用户

    Returns:
        EpisodicRecord 列表（按时间降序）
    """
    conn = _ensure_db()
    if not conn:
        return _recent_from_file(limit, event_type)

    try:
        query = "SELECT * FROM memory_events"
        conditions = []
        params: list[Any] = []

        if event_type and event_type != "all":
            conditions.append("event_type = ?")
            params.append(event_type)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [EpisodicRecord.from_row(r) for r in rows]
    except sqlite3.Error as e:
        _log.warning("查询 memory_events 失败: %s", e)
        return _recent_from_file(limit, event_type)
    finally:
        conn.close()


def search_memory(
    query: str,
    limit: int = 10,
    event_type: str | None = None,
) -> list[EpisodicRecord]:
    """FTS5 全文搜索记忆.

    Args:
        query: 搜索关键词
        limit: 返回条数
        event_type: 可选筛选类型

    Returns:
        匹配的 EpisodicRecord 列表
    """
    conn = _ensure_db()
    if not conn:
        return []

    try:
        # FTS5 搜索
        fts_query = " OR ".join(f'"{word}"' for word in query.split() if len(word) > 0)
        if not fts_query:
            return []

        sql = """
            SELECT me.* FROM memory_events me
            JOIN memory_fts mf ON me.rowid = mf.rowid
            WHERE memory_fts MATCH ?
        """
        params: list[Any] = [fts_query]

        if event_type and event_type != "all":
            sql += " AND me.event_type = ?"
            params.append(event_type)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [EpisodicRecord.from_row(r) for r in rows]
    except sqlite3.Error as e:
        _log.warning("FTS 搜索失败: %s", e)
        return []
    finally:
        conn.close()


def get_event_by_id(event_id: str) -> EpisodicRecord | None:
    """按 ID 获取单条记忆.

    Args:
        event_id: 事件 ID

    Returns:
        EpisodicRecord 或 None
    """
    conn = _ensure_db()
    if not conn:
        return None

    try:
        row = conn.execute(
            "SELECT * FROM memory_events WHERE id = ?", [event_id]
        ).fetchone()
        if row:
            return EpisodicRecord.from_row(row)
        return None
    except sqlite3.Error as e:
        _log.warning("查询单条记忆失败: %s", e)
        return None
    finally:
        conn.close()


def get_stats() -> dict:
    """获取记忆系统统计摘要.

    Returns:
        统计字典，包含各类事件计数和最近活跃时间
    """
    conn = _ensure_db()
    if not conn:
        return {"error": "memory db 不可用", "total": 0}

    try:
        total = conn.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0]

        type_counts = {}
        for row in conn.execute(
            "SELECT event_type, COUNT(*) as cnt FROM memory_events GROUP BY event_type"
        ).fetchall():
            type_counts[row[0]] = row[1]

        last_record = conn.execute(
            "SELECT created_at, summary FROM memory_events ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

        return {
            "total": total,
            "by_type": type_counts,
            "last_event_at": last_record[0] if last_record else None,
            "last_event_summary": last_record[1] if last_record else None,
        }
    except sqlite3.Error as e:
        _log.warning("统计查询失败: %s", e)
        return {"error": str(e), "total": 0}
    finally:
        conn.close()


def recent_context(limit: int = 5) -> str:
    """生成最近记忆的上下文文本，供 LLM 注入 system prompt.

    Args:
        limit: 包含最近 N 条

    Returns:
        markdown 格式的上下文文本
    """
    events = recent_events(limit=limit)
    if not events:
        return ""

    lines = ["## 最近操作记录", ""]
    for e in events:
        icon = {"query": "🔍", "ingest": "📥", "lint": "🔬", "system": "⚙️", "synthesis": "📝"}.get(e.event_type, "•")
        lines.append(f"- {icon} [{e._date_str()}] {e.summary}")
        if e.pages:
            page_links = "、".join(f"[[{p}]]" for p in e.pages[:3])
            lines.append(f"  涉及: {page_links}")
    lines.append("")

    return "\n".join(lines)


# ---- Fallback：从文件读取（SQLite 不可用时） ----

def _recent_from_file(limit: int = 10, event_type: str | None = None) -> list[EpisodicRecord]:
    """从操作日志.md 解析最近记录（SQLite 降级方案）."""
    import re

    if not OPERATION_LOG.exists():
        return []

    content = OPERATION_LOG.read_text(encoding="utf-8")
    body = strip_frontmatter(content)

    # 匹配日志条目
    pattern = r"## \[(\d{4}-\d{2}-\d{2})\]\s+(\w+)\s*\|\s*(.+?)(?=\n## \[|\Z)"
    matches = re.findall(pattern, body, re.DOTALL)

    records = []
    for date_str, etype, details in matches[:limit]:
        if event_type and etype != event_type:
            continue

        lines = details.strip().split("\n")
        summary = lines[0][:80] if lines else ""
        pages = list(set(re.findall(r"\[\[([^\]]+)\]\]", details)))

        records.append(EpisodicRecord(
            id=f"file-{date_str}-{etype}",
            event_type=etype,
            summary=summary,
            details=details.strip()[:2000],
            pages=pages,
            source="file",
            created_at=date_str,
        ))

    return records
