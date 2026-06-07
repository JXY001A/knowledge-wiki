"""测试 memory/models.py — 数据模型序列化."""

import json
import pytest
from knowledge_wiki.memory.models import EpisodicRecord, uuid7, now_iso


def test_uuid7_is_unique():
    """UUID7 应生成唯一值."""
    ids = {uuid7() for _ in range(100)}
    assert len(ids) == 100


def test_uuid7_format():
    """UUID7 应符合标准格式."""
    uid = uuid7()
    parts = uid.split("-")
    assert len(parts) == 5
    assert len(parts[0]) == 8  # timestamp high
    assert parts[2][0] == "7"   # version nibble


def test_now_iso_format():
    """now_iso 应返回 ISO8601 格式."""
    ts = now_iso()
    assert "T" in ts
    assert "+00:00" in ts or "Z" in ts


def test_episodic_record_defaults():
    """默认创建的记录应有合法字段."""
    record = EpisodicRecord(event_type="query", summary="测试")
    assert record.id  # 自动生成
    assert record.event_type == "query"
    assert record.summary == "测试"
    assert record.pages == []
    assert record.concepts == []
    assert record.tags == []
    assert record.created_at  # 自动生成


def test_episodic_record_to_dict():
    """to_dict 应将 list 字段序列化为 JSON 字符串."""
    record = EpisodicRecord(
        event_type="ingest",
        summary="测试摄取",
        pages=["测试页面"],
        concepts=["MCP"],
        tags=["测试"],
    )
    d = record.to_dict()
    assert isinstance(d["pages"], str)
    assert json.loads(d["pages"]) == ["测试页面"]
    assert json.loads(d["tags"]) == ["测试"]


def test_episodic_record_to_markdown():
    """to_markdown 应生成可读日志条目."""
    record = EpisodicRecord(
        event_type="query",
        summary="AI Workflow 是什么",
        pages=["AI Workflow"],
        concepts=["AI Workflow"],
        domain="AI平台",
        score=4,
    )
    md = record.to_markdown()
    assert "## [" in md
    assert "query" in md
    assert "AI Workflow" in md
    assert "⭐" in md


def test_episodic_record_from_row():
    """from_row 应从 sqlite3.Row 正确构造."""
    import sqlite3
    import tempfile
    from pathlib import Path

    # 用临时数据库测试 roundtrip
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE memory_events (
                id TEXT PRIMARY KEY,
                event_type TEXT,
                summary TEXT,
                details TEXT,
                pages TEXT DEFAULT '[]',
                concepts TEXT DEFAULT '[]',
                score INTEGER,
                user_id TEXT DEFAULT '',
                source TEXT DEFAULT 'unknown',
                domain TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                created_at TEXT
            )
        """)

        record = EpisodicRecord(
            event_type="query",
            summary="测试查询",
            pages=["页面A", "页面B"],
            concepts=["概念X"],
            tags=["标签1"],
        )
        d = record.to_dict()
        columns = ", ".join(d.keys())
        placeholders = ", ".join("?" for _ in d)
        conn.execute(
            f"INSERT INTO memory_events ({columns}) VALUES ({placeholders})",
            list(d.values()),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM memory_events").fetchone()
        restored = EpisodicRecord.from_row(row)
        assert restored.event_type == "query"
        assert restored.pages == ["页面A", "页面B"]
        assert restored.concepts == ["概念X"]
        assert restored.tags == ["标签1"]
