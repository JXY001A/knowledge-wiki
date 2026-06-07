/* WARNING: Script requires that SQLITE_DBCONFIG_DEFENSIVE be disabled */
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            );
INSERT INTO schema_version VALUES(1,'2026-06-07T10:27:03.793347','初始 schema：memory_events + FTS5 全文索引');
CREATE TABLE memory_events (
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
INSERT INTO memory_events VALUES('019e9fe7-b7f1-77da5-f812-aab5e901bb40','query','测试查询：MCP 协议是什么？','测试查询：MCP 协议是什么？','["MCP（Model Context Protocol）"]','["MCP"]',NULL,'test','wecom','','["查询"]','2026-06-07T02:27:03.793408+00:00');
PRAGMA writable_schema=ON;
INSERT INTO sqlite_schema(type,name,tbl_name,rootpage,sql)VALUES('table','memory_fts','memory_fts',0,'CREATE VIRTUAL TABLE memory_fts USING fts5(
    summary, details, content=memory_events, content_rowid=rowid
)');
CREATE TABLE IF NOT EXISTS 'memory_fts_data'(id INTEGER PRIMARY KEY, block BLOB);
INSERT INTO memory_fts_data VALUES(1,X'010303');
INSERT INTO memory_fts_data VALUES(10,X'000000000101010001010101');
INSERT INTO memory_fts_data VALUES(137438953473,X'0000003a04306d6370010803010103010fe58d8fe8aeaee698afe4bb80e4b988010804010104010ce6b58be8af95e69fa5e8afa2010802010102040b17');
CREATE TABLE IF NOT EXISTS 'memory_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;
INSERT INTO memory_fts_idx VALUES(1,X'',2);
CREATE TABLE IF NOT EXISTS 'memory_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);
INSERT INTO memory_fts_docsize VALUES(1,X'0303');
CREATE TABLE IF NOT EXISTS 'memory_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;
INSERT INTO memory_fts_config VALUES('version',4);
CREATE TRIGGER memory_ai AFTER INSERT ON memory_events BEGIN
    INSERT INTO memory_fts(rowid, summary, details)
    VALUES (new.rowid, new.summary, new.details);
END;
CREATE TRIGGER memory_ad AFTER DELETE ON memory_events BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, summary, details)
    VALUES ('delete', old.rowid, old.summary, old.details);
END;
CREATE TRIGGER memory_au AFTER UPDATE ON memory_events BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, summary, details)
    VALUES ('delete', old.rowid, old.summary, old.details);
    INSERT INTO memory_fts(rowid, summary, details)
    VALUES (new.rowid, new.summary, new.details);
END;
CREATE INDEX idx_memory_type ON memory_events(event_type);
CREATE INDEX idx_memory_created ON memory_events(created_at);
CREATE INDEX idx_memory_score ON memory_events(score);
CREATE INDEX idx_memory_domain ON memory_events(domain);
PRAGMA writable_schema=OFF;
COMMIT;
