"""记忆数据库 — SQLite 连接管理、schema 迁移、WAL 模式.

数据库文件：wiki/.data/memory.db（不入 git，从文件日志可重建）

设计原则：
    - SQLite 是辅助索引，主数据仍在 markdown 文件中
    - 崩溃恢复：从操作日志.md 重建 SQLite
    - WAL 模式：写不阻塞读，崩溃自动恢复
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from knowledge_wiki.config import settings

# 数据库文件路径
DB_PATH = settings.wiki_root / "wiki" / ".data" / "memory.db"

# ============================================================================
# Schema V1 — 初始版本
# ============================================================================

SCHEMA_V1 = """
-- 记忆事件主表
CREATE TABLE IF NOT EXISTS memory_events (
    id          TEXT PRIMARY KEY,       -- UUID7（时间有序）
    event_type  TEXT NOT NULL,          -- 'query' | 'ingest' | 'lint' | 'note' | 'system' | 'synthesis'
    summary     TEXT NOT NULL,          -- 一句话摘要
    details     TEXT,                   -- 详细内容（markdown）
    pages       TEXT NOT NULL DEFAULT '[]',  -- JSON array: 涉及的 wiki 页面
    concepts    TEXT NOT NULL DEFAULT '[]',  -- JSON array: 涉及的概念
    score       INTEGER,               -- 自评分（1-5），NULL = 未评估
    user_id     TEXT DEFAULT '',        -- 触发用户（企微 UserID 或 'system'）
    source      TEXT DEFAULT 'unknown', -- 'wecom' | 'mcp' | 'cli' | 'auto'
    domain      TEXT DEFAULT '',        -- 知识领域
    tags        TEXT NOT NULL DEFAULT '[]', -- JSON array: 标签
    created_at  TEXT NOT NULL           -- ISO8601 时间戳
);

-- 查询索引
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_events(event_type);
CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_events(created_at);
CREATE INDEX IF NOT EXISTS idx_memory_score ON memory_events(score);
CREATE INDEX IF NOT EXISTS idx_memory_domain ON memory_events(domain);

-- FTS5 全文搜索（中文分词由 jieba 在写入时预处理）
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    summary, details, content=memory_events, content_rowid=rowid
);

-- FTS 同步触发器
CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory_events BEGIN
    INSERT INTO memory_fts(rowid, summary, details)
    VALUES (new.rowid, new.summary, new.details);
END;

CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory_events BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, summary, details)
    VALUES ('delete', old.rowid, old.summary, old.details);
END;

CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory_events BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, summary, details)
    VALUES ('delete', old.rowid, old.summary, old.details);
    INSERT INTO memory_fts(rowid, summary, details)
    VALUES (new.rowid, new.summary, new.details);
END;

-- Schema 版本管理
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL,
    description TEXT
);
"""

# 迁移列表：[版本号, SQL, 描述]
MIGRATIONS = [
    (1, SCHEMA_V1, "初始 schema：memory_events + FTS5 全文索引"),
]


def get_db() -> sqlite3.Connection:
    """获取数据库连接（自动启用 WAL + 外键）.

    Returns:
        sqlite3.Connection，已配置 WAL 模式和外键约束
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")       # 写不阻塞读
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection | None = None) -> int:
    """初始化或迁移数据库 schema.

    Args:
        conn: 数据库连接，None 则自动创建

    Returns:
        当前 schema 版本号
    """
    should_close = conn is None
    if conn is None:
        conn = get_db()

    try:
        # 确保 schema_version 表存在
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            )
        """)

        # 获取当前版本
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_ver = row[0] if row and row[0] else 0

        # 执行增量迁移
        for ver, sql, desc in MIGRATIONS:
            if ver > current_ver:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                    [ver, datetime.now().isoformat(), desc],
                )
                current_ver = ver

        conn.commit()
        return current_ver
    finally:
        if should_close:
            conn.close()


def rebuild_from_log(log_path: Path | None = None) -> int:
    """从操作日志.md 重建 SQLite 数据库（灾难恢复）.

    Args:
        log_path: 操作日志路径，默认 wiki/操作日志.md

    Returns:
        重建的记录数
    """
    import re
    from knowledge_wiki.wiki.frontmatter import strip_frontmatter

    if log_path is None:
        log_path = settings.wiki_root / "wiki" / "操作日志.md"

    if not log_path.exists():
        return 0

    conn = get_db()
    init_schema(conn)

    content = log_path.read_text(encoding="utf-8")
    body = strip_frontmatter(content)

    # 解析日志条目：## [YYYY-MM-DD] <event_type> | <summary>
    pattern = r"## \[(\d{4}-\d{2}-\d{2})\]\s+(\w+)\s*\|\s*(.+?)(?=\n## \[|\Z)"
    matches = re.findall(pattern, body, re.DOTALL)

    count = 0
    for date_str, event_type, details in matches:
        detail_text = details.strip()
        summary = detail_text.split("\n")[0][:80] if detail_text else ""

        # 提取 wikilink 引用
        pages = list(set(re.findall(r"\[\[([^\]]+)\]\]", detail_text)))

        try:
            conn.execute(
                """INSERT OR IGNORE INTO memory_events
                   (id, event_type, summary, details, pages, source, created_at)
                   VALUES (?, ?, ?, ?, ?, 'auto', ?)""",
                [
                    f"rebuilt-{date_str}-{count}",
                    event_type,
                    summary,
                    detail_text[:2000],
                    str(pages).replace("'", '"'),
                    f"{date_str}T00:00:00",
                ],
            )
            count += 1
        except sqlite3.Error:
            pass

    conn.commit()
    conn.close()
    return count
