/* WARNING: Script requires that SQLITE_DBCONFIG_DEFENSIVE be disabled */
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            );
INSERT INTO schema_version VALUES(1,'2026-06-07T11:53:54.944386','初始 schema：todos/reminders/notes/bookmarks/habits/habit_logs/push_queue');
CREATE TABLE todos (
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
INSERT INTO todos VALUES('019ea037-3c00-77ebd-bbaf-4eecbf1715bb','测试待办','','pending','high','2026-06-10',NULL,'["工作"]','wecom','2026-06-07T03:53:54.944469+00:00','2026-06-07T03:53:54.944583+00:00');
CREATE TABLE reminders (
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
INSERT INTO reminders VALUES('019ea037-3c00-777a2-a58f-3746f1c84168',NULL,'早会提醒','2026-06-08T09:00:00',NULL,'active',NULL,'2026-06-07T03:53:54.944723+00:00');
CREATE TABLE notes (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    related_page TEXT,
    source      TEXT DEFAULT 'wecom',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
INSERT INTO notes VALUES('019ea037-3c00-77c8c-511b-d80e1447e3db','部署脚本 health check 超时设置','["DevMechin", "运维"]','','wecom','2026-06-07T03:53:54.944838+00:00','2026-06-07T03:53:54.944840+00:00');
PRAGMA writable_schema=ON;
INSERT INTO sqlite_schema(type,name,tbl_name,rootpage,sql)VALUES('table','notes_fts','notes_fts',0,'CREATE VIRTUAL TABLE notes_fts USING fts5(
    content, tags, content=notes, content_rowid=rowid
)');
CREATE TABLE IF NOT EXISTS 'notes_fts_data'(id INTEGER PRIMARY KEY, block BLOB);
INSERT INTO notes_fts_data VALUES(1,X'010402');
INSERT INTO notes_fts_data VALUES(10,X'000000000101010001010101');
INSERT INTO notes_fts_data VALUES(137438953473,X'000000570630636865636b01020401096465766d656368696e010601010201066865616c7468010203010ce8b685e697b6e8aebee7bdae0102050205bf90e7bbb40106010103010ce983a8e7bdb2e8849ae69cac010202040a100b110c');
CREATE TABLE IF NOT EXISTS 'notes_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;
INSERT INTO notes_fts_idx VALUES(1,X'',2);
CREATE TABLE IF NOT EXISTS 'notes_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);
INSERT INTO notes_fts_docsize VALUES(1,X'0402');
CREATE TABLE IF NOT EXISTS 'notes_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;
INSERT INTO notes_fts_config VALUES('version',4);
CREATE TABLE bookmarks (
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
CREATE TABLE habits (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    unit        TEXT DEFAULT 'boolean',             -- boolean|count|duration
    target      REAL,
    created_at  TEXT NOT NULL,
    archived_at TEXT
);
CREATE TABLE habit_logs (
    id          TEXT PRIMARY KEY,
    habit_id    TEXT NOT NULL,
    date        TEXT NOT NULL,
    value       REAL NOT NULL,
    note        TEXT,
    FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE,
    UNIQUE(habit_id, date)
);
CREATE TABLE push_queue (
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
CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
END;
CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content, tags) VALUES ('delete', old.rowid, old.content, old.tags);
END;
CREATE TRIGGER notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content, tags) VALUES ('delete', old.rowid, old.content, old.tags);
    INSERT INTO notes_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
END;
CREATE INDEX idx_todos_status ON todos(status);
CREATE INDEX idx_todos_deadline ON todos(deadline);
CREATE INDEX idx_todos_priority ON todos(priority);
CREATE INDEX idx_todos_created ON todos(created_at);
CREATE INDEX idx_reminders_trigger ON reminders(trigger_at, status);
CREATE INDEX idx_bookmarks_status ON bookmarks(read_status);
CREATE INDEX idx_habit_logs_date ON habit_logs(date);
CREATE INDEX idx_habit_logs_habit ON habit_logs(habit_id, date);
CREATE INDEX idx_push_queue_next ON push_queue(next_retry_at, status);
PRAGMA writable_schema=OFF;
COMMIT;
