"""测试 memory/db.py — SQLite schema 初始化与迁移."""

import pytest
from knowledge_wiki.memory.db import get_db, init_schema


def test_init_schema_creates_tables(tmp_path, monkeypatch):
    """初始化 schema 应创建所有表."""
    monkeypatch.setattr(
        "knowledge_wiki.memory.db.DB_PATH",
        tmp_path / "test_memory.db",
    )

    conn = get_db()
    ver = init_schema(conn)

    assert ver == 1

    # 验证核心表存在
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {r[0] for r in tables}

    assert "memory_events" in table_names
    assert "memory_fts" in table_names
    assert "schema_version" in table_names

    conn.close()


def test_init_schema_idempotent(tmp_path, monkeypatch):
    """重复初始化不应报错."""
    monkeypatch.setattr(
        "knowledge_wiki.memory.db.DB_PATH",
        tmp_path / "test_memory_idem.db",
    )

    conn = get_db()
    v1 = init_schema(conn)  # 第一次
    v2 = init_schema(conn)  # 第二次（幂等）
    assert v1 == v2 == 1
    conn.close()
