"""助理数据库 — SQLite 连接、schema 迁移、WAL 模式.

数据库文件：wiki/.data/assistant.db（不入 git，SQL dump 文件入 git）

表结构：
    todos       — 待办事项（状态变更频繁、条件筛选）
    reminders   — 定时提醒（独立于 todos，也可关联）
    notes       — 快速笔记（短文本、FTS5 全文搜索）
    bookmarks   — 书签（结构化、去重、阅读状态）
    habits      — 习惯定义（名称、单位、目标值）
    habit_logs  — 习惯打卡记录（日期 + 值）
    push_queue  — 消息推送队列（失败重试）
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from knowledge_wiki.config import settings

# 数据库文件路径
DB_PATH = settings.wiki_root / "wiki" / ".data" / "assistant.db"

# ============================================================================
# Schema V1
# ============================================================================

SCHEMA_V1 = """
-- 待办事项
CREATE TABLE IF NOT EXISTS todos (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending|in_progress|done|cancelled
    priority    TEXT NOT NULL DEFAULT 'medium',     -- high|medium|low
    deadline    TEXT,                               -- ISO8601
    completed_at TEXT,
    tags        TEXT NOT NULL DEFAULT '[]',          -- JSON array
    source      TEXT DEFAULT 'wecom',               -- wecom|mcp|cli|auto
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_deadline ON todos(deadline);
CREATE INDEX IF NOT EXISTS idx_todos_priority ON todos(priority);
CREATE INDEX IF NOT EXISTS idx_todos_created ON todos(created_at);

-- 定时提醒
CREATE TABLE IF NOT EXISTS reminders (
    id          TEXT PRIMARY KEY,
    todo_id     TEXT,
    content     TEXT NOT NULL,
    trigger_at  TEXT NOT NULL,
    repeat_rule TEXT,                                -- cron 表达式
    status      TEXT NOT NULL DEFAULT 'active',      -- active|fired|cancelled
    fired_at    TEXT,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (todo_id) REFERENCES todos(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_reminders_trigger ON reminders(trigger_at, status);

-- 快速笔记
CREATE TABLE IF NOT EXISTS notes (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    related_page TEXT,
    source      TEXT DEFAULT 'wecom',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
-- FTS5 全文搜索
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    content, tags, content=notes, content_rowid=rowid
);
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content, tags) VALUES ('delete', old.rowid, old.content, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content, tags) VALUES ('delete', old.rowid, old.content, old.tags);
    INSERT INTO notes_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
END;

-- 书签
CREATE TABLE IF NOT EXISTS bookmarks (
    id          TEXT PRIMARY KEY,
    url         TEXT NOT NULL UNIQUE,
    title       TEXT,
    description TEXT,
    tags        TEXT NOT NULL DEFAULT '[]',
    read_status TEXT DEFAULT 'unread',              -- unread|reading|read
    ingested    INTEGER DEFAULT 0,
    wiki_page   TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bookmarks_status ON bookmarks(read_status);

-- 习惯追踪
CREATE TABLE IF NOT EXISTS habits (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    unit        TEXT DEFAULT 'boolean',             -- boolean|count|duration
    target      REAL,
    created_at  TEXT NOT NULL,
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS habit_logs (
    id          TEXT PRIMARY KEY,
    habit_id    TEXT NOT NULL,
    date        TEXT NOT NULL,
    value       REAL NOT NULL,
    note        TEXT,
    FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE,
    UNIQUE(habit_id, date)
);
CREATE INDEX IF NOT EXISTS idx_habit_logs_date ON habit_logs(date);
CREATE INDEX IF NOT EXISTS idx_habit_logs_habit ON habit_logs(habit_id, date);

-- 消息推送队列
CREATE TABLE IF NOT EXISTS push_queue (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    content     TEXT NOT NULL,
    msg_type    TEXT DEFAULT 'markdown',            -- markdown|text|template_card
    status      TEXT DEFAULT 'pending',             -- pending|sent|failed
    retries     INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    last_error  TEXT,
    created_at  TEXT NOT NULL,
    next_retry_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_queue_next ON push_queue(next_retry_at, status);

-- Schema 版本
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL,
    description TEXT
);
"""

SCHEMA_V2 = """
ALTER TABLE reminders ADD COLUMN user_id TEXT DEFAULT '';
"""

MIGRATIONS = [
    (1, SCHEMA_V1, "初始 schema：todos/reminders/notes/bookmarks/habits/habit_logs/push_queue"),
    (2, SCHEMA_V2, "reminders 表添加 user_id 列（主动推送需要）"),
]


def get_db() -> sqlite3.Connection:
    """获取数据库连接（WAL 模式）."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection | None = None) -> int:
    """初始化或迁移 schema."""
    should_close = conn is None
    if conn is None:
        conn = get_db()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            )
        """)
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_ver = row[0] if row and row[0] else 0

        for ver, sql, desc in MIGRATIONS:
            if ver > current_ver:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_version VALUES (?, ?, ?)",
                    [ver, datetime.now().isoformat(), desc],
                )
                current_ver = ver

        conn.commit()
        return current_ver
    finally:
        if should_close:
            conn.close()
