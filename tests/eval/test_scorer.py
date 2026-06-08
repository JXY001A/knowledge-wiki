"""评估引擎单元测试 — EvalResult 数据类."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from knowledge_wiki.eval.scorer import EvalResult, get_eval_stats


class TestEvalResult:
    """EvalResult 数据类测试."""

    def test_default_values(self):
        r = EvalResult()
        assert r.accuracy == 3
        assert r.completeness == 3
        assert r.usefulness == 3
        assert r.overall == 3
        assert r.gaps == []
        assert r.improvement == ""

    def test_from_json_perfect(self):
        data = {"accuracy": 5, "completeness": 5, "usefulness": 5,
                "gaps": [], "improvement": "完美"}
        r = EvalResult.from_json(data)
        assert r.accuracy == 5
        assert r.overall == 5
        assert r.stars == "⭐⭐⭐⭐⭐"
        assert r.is_good is True

    def test_from_json_poor(self):
        data = {"accuracy": 2, "completeness": 1, "usefulness": 2,
                "gaps": ["缺少 MCP 协议资料"], "improvement": "补充 MCP 文档"}
        r = EvalResult.from_json(data)
        assert r.overall == 2  # round((2+1+2)/3) = round(1.67) = 2
        assert r.stars == "⭐⭐"
        assert r.is_good is False
        assert r.has_gaps is True
        assert "MCP" in r.gaps[0]

    def test_from_json_clamps_values(self):
        """评分超出 1-5 范围应被钳制."""
        data = {"accuracy": 10, "completeness": 0, "usefulness": 5}
        r = EvalResult.from_json(data)
        assert r.accuracy == 5
        assert r.completeness == 1
        assert r.usefulness == 5

    def test_from_json_missing_fields_defaults(self):
        """缺失字段使用默认值."""
        r = EvalResult.from_json({})
        assert r.accuracy == 3
        assert r.completeness == 3
        assert r.gaps == []

    def test_overall_rounding(self):
        """综合分应正确四舍五入."""
        data = {"accuracy": 4, "completeness": 4, "usefulness": 3}
        r = EvalResult.from_json(data)
        assert r.overall == 4  # round(11/3) = 4

    def test_has_gaps_empty_list(self):
        r = EvalResult(gaps=[])
        assert r.has_gaps is False

    def test_raw_field_stored(self):
        data = {"accuracy": 3, "completeness": 3, "usefulness": 3,
                "gaps": [], "improvement": ""}
        r = EvalResult.from_json(data)
        parsed = json.loads(r.raw)
        assert parsed["accuracy"] == 3


class TestGetEvalStats:
    """get_eval_stats 测试."""

    def test_empty_db_returns_zero(self):
        """空数据库返回 0 评估."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with patch("knowledge_wiki.eval.scorer.settings") as mock_settings:
                mock_settings.wiki_root = Path(tmp)
                with patch("knowledge_wiki.memory.db.DB_PATH", db_path):
                    stats = get_eval_stats()
                    assert stats["total"] == 0
                    assert stats["avg_score"] == 0
                    assert "暂无评估数据" in stats.get("message", "")
