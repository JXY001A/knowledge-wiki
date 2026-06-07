"""记忆写入器 — 结构化日志的双写（文件 + SQLite）.

所有写入操作自动双写：
    1. SQLite memory_events 表（结构化查询）
    2. wiki/操作日志.md markdown 文件（人类可读 + Git 版本控制）

双写不互锁：SQLite 写入失败不影响文件写入，反之亦然。
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from knowledge_wiki.config import settings
from knowledge_wiki.memory.models import EpisodicRecord, now_iso
from knowledge_wiki.memory.db import get_db, init_schema
from knowledge_wiki.wiki.atomic import atomic_update

_log = logging.getLogger(__name__)

# 操作日志文件路径
OPERATION_LOG = settings.wiki_root / "wiki" / "操作日志.md"


def _ensure_db() -> sqlite3.Connection | None:
    """获取数据库连接，初始化 schema。失败返回 None."""
    try:
        conn = get_db()
        init_schema(conn)
        return conn
    except sqlite3.Error as e:
        _log.warning("memory db 不可用，跳过 SQLite 写入: %s", e)
        return None


# ---- 核心写入 ----

def record_event(record: EpisodicRecord) -> str:
    """写入一条结构化记忆记录（双写）.

    Args:
        record: EpisodicRecord 实例

    Returns:
        记录 ID
    """
    # 1. 写 SQLite（快速失败，不阻塞文件写入）
    conn = _ensure_db()
    if conn:
        try:
            d = record.to_dict()
            columns = ", ".join(d.keys())
            placeholders = ", ".join("?" for _ in d)
            conn.execute(
                f"INSERT INTO memory_events ({columns}) VALUES ({placeholders})",
                list(d.values()),
            )
            conn.commit()
        except sqlite3.Error as e:
            _log.warning("写 memory_events 失败: %s", e)
        finally:
            conn.close()

    # 2. 写文件日志（追加到操作日志.md 顶部）
    _append_to_operation_log(record)

    return record.id


def record_query(
    question: str,
    pages: list[str],
    concepts: list[str],
    user_id: str = "",
    source: str = "wecom",
    score: int | None = None,
) -> str:
    """记录一次知识查询事件.

    Args:
        question: 用户问题
        pages: 检索到的 wiki 页面列表
        concepts: 涉及的概念
        user_id: 用户标识
        source: 来源（wecom/mcp/cli）
        score: 自评分（可选）

    Returns:
        记录 ID
    """
    record = EpisodicRecord(
        event_type="query",
        summary=question[:80],
        details=question,
        pages=pages,
        concepts=concepts,
        user_id=user_id,
        source=source,
        score=score,
        tags=["查询"],
    )
    return record_event(record)


def record_ingest(
    title: str,
    domain: str = "",
    concepts: list[str] | None = None,
    pages: list[str] | None = None,
    user_id: str = "",
    source: str = "wecom",
) -> str:
    """记录一次知识摄取事件.

    Args:
        title: 资料标题
        domain: 知识领域
        concepts: 新提取的概念
        pages: 新建/更新的 wiki 页面
        user_id: 用户标识
        source: 来源

    Returns:
        记录 ID
    """
    record = EpisodicRecord(
        event_type="ingest",
        summary=title[:80],
        details=f"摄取资料：{title}",
        domain=domain,
        concepts=concepts or [],
        pages=pages or [],
        user_id=user_id,
        source=source,
        tags=["摄取", domain] if domain else ["摄取"],
    )
    return record_event(record)


def record_lint(
    findings_summary: str,
    broken_links: int = 0,
    orphans: int = 0,
    stale_pages: int = 0,
    user_id: str = "",
    source: str = "auto",
) -> str:
    """记录一次健康检查事件.

    Args:
        findings_summary: 检查结果摘要
        broken_links: 死链数
        orphans: 孤页数
        stale_pages: 过时页面数
        user_id: 用户标识
        source: 来源

    Returns:
        记录 ID
    """
    details = (
        f"健康检查结果：\n"
        f"- 死链：{broken_links}\n"
        f"- 孤页：{orphans}\n"
        f"- 过时页面：{stale_pages}\n"
        f"\n{findings_summary}"
    )
    record = EpisodicRecord(
        event_type="lint",
        summary=f"健康检查：死链{broken_links} 孤页{orphans} 过时{stale_pages}",
        details=details,
        user_id=user_id,
        source=source,
        tags=["健康检查"],
    )
    return record_event(record)


def record_system_event(
    summary: str,
    details: str = "",
    tags: list[str] | None = None,
) -> str:
    """记录系统事件（备份、部署、错误等）.

    Args:
        summary: 事件摘要
        details: 详细描述
        tags: 标签

    Returns:
        记录 ID
    """
    record = EpisodicRecord(
        event_type="system",
        summary=summary[:80],
        details=details,
        user_id="system",
        source="auto",
        tags=tags or ["系统"],
    )
    return record_event(record)


# ---- 文件日志辅助 ----

def _append_to_operation_log(record: EpisodicRecord) -> None:
    """将记忆记录追加到操作日志.md（人类可读格式）."""
    if not OPERATION_LOG.exists():
        _log.warning("操作日志.md 不存在，跳过文件写入")
        return

    try:
        markdown_entry = record.to_markdown()

        def _transform(content: str) -> str:
            marker = "> 每次 ingest / query / lint"
            pos = content.find(marker)
            if pos != -1:
                insert_at = content.find("\n", pos) + 1
                if insert_at < len(content) and content[insert_at] == "\n":
                    insert_at += 1
            else:
                insert_at = len(content)
            return content[:insert_at] + markdown_entry + "\n" + content[insert_at:]

        atomic_update(OPERATION_LOG, _transform)
    except Exception as e:
        _log.warning("写操作日志.md 失败: %s", e)
