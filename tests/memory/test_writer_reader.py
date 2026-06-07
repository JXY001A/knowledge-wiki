"""测试 memory/writer.py + reader.py — 写入与查询集成."""

import pytest
from knowledge_wiki.memory import (
    init_schema, get_db,
    record_query, record_ingest, record_lint,
    recent_events, search_memory, get_stats,
)


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    """临时 memory 数据库."""
    monkeypatch.setattr(
        "knowledge_wiki.memory.db.DB_PATH",
        tmp_path / "test_memory.db",
    )
    monkeypatch.setattr(
        "knowledge_wiki.memory.writer.OPERATION_LOG",
        tmp_path / "test_log.md",
    )
    # 初始化
    conn = get_db()
    init_schema(conn)
    conn.close()
    return tmp_path


def test_record_query(memory_db):
    """写入查询应成功且可读回."""
    rid = record_query(
        "什么是 MCP？",
        pages=["MCP（Model Context Protocol）"],
        concepts=["MCP"],
        user_id="test_user",
    )
    assert rid

    # 读回
    events = recent_events(limit=10)
    found = [e for e in events if e.id == rid]
    assert len(found) == 1
    assert found[0].event_type == "query"
    assert "MCP" in found[0].summary


def test_record_ingest(memory_db):
    """写入摄取事件并验证."""
    rid = record_ingest(
        "资料摘要：Claude Code 最佳实践",
        domain="AI平台",
        concepts=["Claude Code", "Agent"],
        pages=["资料摘要：Claude Code 最佳实践", "Claude Code"],
        user_id="test_user",
    )
    assert rid

    events = recent_events(limit=10, event_type="ingest")
    assert len(events) >= 1
    assert events[0].domain == "AI平台"


def test_record_lint(memory_db):
    """写入健康检查事件并验证."""
    rid = record_lint(
        "发现 3 条死链",
        broken_links=3,
        orphans=2,
        stale_pages=1,
    )
    assert rid

    events = recent_events(limit=10, event_type="lint")
    assert len(events) >= 1


def test_recent_events_filter(memory_db):
    """recent_events 应按类型筛选."""
    record_query("查询1", pages=[], concepts=[])
    record_query("查询2", pages=[], concepts=[])
    record_ingest("摄取1", concepts=[], pages=[])

    queries = recent_events(limit=10, event_type="query")
    assert all(e.event_type == "query" for e in queries)
    assert len(queries) >= 2


def test_search_memory(memory_db):
    """FTS 全文搜索应找到匹配项."""
    record_query("测试 MCP 协议", pages=[], concepts=["MCP"])
    record_query("测试 Ollama 部署", pages=[], concepts=["Ollama"])

    results = search_memory("MCP")
    assert len(results) >= 1
    assert any("MCP" in r.summary for r in results)


def test_get_stats(memory_db):
    """统计应反映实际数据."""
    record_query("q1", pages=[], concepts=[])
    record_query("q2", pages=[], concepts=[])
    record_ingest("i1", concepts=[], pages=[])

    stats = get_stats()
    assert stats["total"] >= 3
    assert "query" in stats["by_type"]
    assert "ingest" in stats["by_type"]


def test_multiple_records(memory_db):
    """大量写入不应出错."""
    for i in range(20):
        record_query(f"测试查询 #{i}", pages=[], concepts=[])

    events = recent_events(limit=50)
    assert len(events) >= 20
