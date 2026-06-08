"""知识缺口检测单元测试 — gap extraction 和 detect_gaps."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from knowledge_wiki.evolve.gap_detector import (
    _extract_gaps_from_text,
    generate_ingest_list,
)


class TestExtractGapsFromText:
    """_extract_gaps_from_text 测试."""

    def test_json_format(self):
        """从 JSON 中提取缺口."""
        text = '评估结果：{"gaps": ["缺少 RAG 资料", "缺少 Agent 资料"], "improvement": "补充"}'
        gaps = _extract_gaps_from_text(text)
        assert "缺少 RAG 资料" in gaps
        assert "缺少 Agent 资料" in gaps

    def test_natural_language_format(self):
        """从自然语言中提取缺口."""
        text = "知识缺口：MCP协议、Agent技能、上下文隔离"
        gaps = _extract_gaps_from_text(text)
        assert "MCP协议" in gaps
        assert "Agent技能" in gaps
        assert "上下文隔离" in gaps

    def test_colon_separator(self):
        """支持半角冒号."""
        text = "知识缺口: 深度学习, 强化学习"
        gaps = _extract_gaps_from_text(text)
        assert len(gaps) >= 1

    def test_empty_text(self):
        """空文本返回空列表."""
        gaps = _extract_gaps_from_text("")
        assert gaps == []

    def test_no_gaps_in_text(self):
        """无缺口标记."""
        gaps = _extract_gaps_from_text("一切正常")
        assert gaps == []

    def test_short_items_filtered(self):
        """过短的缺口项被过滤."""
        text = "知识缺口：A, B"
        gaps = _extract_gaps_from_text(text)
        # "A" 和 "B" 长度 ≤2，应被过滤
        assert len(gaps) == 0

    def test_max_five_gaps(self):
        """最多返回 5 个缺口."""
        text = "知识缺口：" + "、".join(f"gap{i}" for i in range(10))
        gaps = _extract_gaps_from_text(text)
        assert len(gaps) <= 5


class TestGenerateIngestList:
    """generate_ingest_list 测试."""

    def test_returns_structured_dict(self):
        """返回结构化字典 — 使用真实 SQLite 数据库避免 mock 复杂度."""
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            wiki_root = Path(tmp)
            db_path = wiki_root / "test.db"
            (wiki_root / "raw").mkdir(parents=True, exist_ok=True)
            (wiki_root / "raw" / "test.md").write_text("# test")
            (wiki_root / "wiki").mkdir(parents=True, exist_ok=True)

            # 创建真实的内存数据库（通过 :memory: 不行，需要文件路径给 get_db）
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            from knowledge_wiki.memory.db import init_schema
            init_schema(conn)
            conn.commit()
            conn.close()

            with patch("knowledge_wiki.config.settings") as ms:
                ms.wiki_root = wiki_root
                with patch("knowledge_wiki.memory.db.DB_PATH", db_path):
                    with patch("knowledge_wiki.memory.semantic.concept_coverage",
                               return_value={"missing_concepts": []}):
                        with patch("knowledge_wiki.wiki.search.get_all_page_titles",
                                   return_value=[]):
                            result = generate_ingest_list()

        assert "gaps" in result
        assert "unprocessed_raw" in result
        assert "missing_concepts" in result
        assert isinstance(result["gaps"], list)
        assert isinstance(result["unprocessed_raw"], list)
