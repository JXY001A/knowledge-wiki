"""assistant 数据库层单元测试 — schema 迁移."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, PropertyMock

from knowledge_wiki.assistant.db import get_db, init_schema, SCHEMA_V1, MIGRATIONS


class TestSchemaMigrations:
    """Schema 版本迁移测试."""

    def test_init_schema_creates_all_tables(self):
        """首次初始化应创建所有表."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        ver = init_schema(conn)
        assert ver == len(MIGRATIONS)

        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r[0] for r in tables}
        for t in ["todos", "reminders", "notes", "bookmarks", "habits",
                   "habit_logs", "push_queue", "conversations",
                   "conversation_messages"]:
            assert t in names, f"Missing table: {t}"
        conn.close()

    def test_init_schema_idempotent(self):
        """重复调用不应报错."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        v1 = init_schema(conn)
        v2 = init_schema(conn)
        assert v1 == v2 == len(MIGRATIONS)
        conn.close()

    def test_init_schema_sets_version(self):
        """迁移后 schema_version 表应有正确版本号."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_schema(conn)

        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert row[0] == len(MIGRATIONS)
        conn.close()

    def test_init_schema_incremental_migration(self):
        """从低版本逐步迁移 — 模拟已有 V1 表结构."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row

        # Simulate V1 state: create schema_version + all V1 tables
        conn.executescript(SCHEMA_V1)
        conn.execute(
            "INSERT INTO schema_version VALUES (?, ?, ?)",
            [1, "2026-01-01", "v1"],
        )
        conn.commit()

        # Run migration — should apply V2 and V3
        ver = init_schema(conn)
        assert ver == len(MIGRATIONS)

        # V2 should have added user_id column to existing reminders table
        cols = [c[1] for c in conn.execute("PRAGMA table_info(reminders)").fetchall()]
        assert "user_id" in cols

        # V3 should have created conversations tables
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in tables}
        assert "conversations" in names

        conn.close()

    def test_get_db_returns_wal_mode(self):
        """get_db 应返回 WAL 模式的连接."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with patch("knowledge_wiki.assistant.db.DB_PATH", db_path):
                conn = get_db()
                row = conn.execute("PRAGMA journal_mode").fetchone()
                assert row[0].upper() == "WAL"
                conn.close()

    def test_get_db_enables_foreign_keys(self):
        """get_db 应启用外键约束."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with patch("knowledge_wiki.assistant.db.DB_PATH", db_path):
                conn = get_db()
                row = conn.execute("PRAGMA foreign_keys").fetchone()
                assert row[0] == 1
                conn.close()
