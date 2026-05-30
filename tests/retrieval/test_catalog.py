"""目录解析与初筛单元测试."""

import tempfile
from pathlib import Path

from knowledge_wiki.wiki.retrieval.catalog import catalog_filter, parse_catalog


SAMPLE_CATALOG = """## 领域页

### AI平台
- [[DeepSeek]]
- [[Ollama]]

## 概念
- [[AI Workflow]]
- [[Agentic Workflow]]

## 综合分析
- [[知识库系统全链路架构]]
"""


class TestParseCatalog:
    """目录解析测试."""

    def test_parses_categories(self):
        """解析类别结构."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(SAMPLE_CATALOG)
            f.flush()
            result = parse_catalog(Path(f.name))
            Path(f.name).unlink()

        assert "AI平台" in result["categories"]
        assert "概念" in result["categories"]
        assert "综合分析" in result["categories"]

    def test_collects_all_titles(self):
        """收集所有页面标题."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(SAMPLE_CATALOG)
            f.flush()
            result = parse_catalog(Path(f.name))
            Path(f.name).unlink()

        assert "DeepSeek" in result["all_titles"]
        assert "AI Workflow" in result["all_titles"]
        assert len(result["all_titles"]) == 5


class TestCatalogFilter:
    """初筛测试."""

    def test_title_hit_ranked(self):
        """标题命中."""
        catalog = {
            "categories": {
                "AI平台": ["DeepSeek", "Ollama"],
                "概念": ["AI Workflow"],
            },
            "all_titles": {"DeepSeek", "Ollama", "AI Workflow"},
        }
        tokens = ["deepseek"]
        candidates = catalog_filter(tokens, catalog, k=10)
        assert "DeepSeek" in candidates

    def test_empty_query_no_results(self):
        """空查询直接返回空."""
        catalog = {
            "categories": {},
            "all_titles": {"DeepSeek", "Ollama"},
        }
        candidates = catalog_filter([], catalog, k=10)
        # 空查询无命中 → 应返回空（catalog_filter 需要至少命中一个 token）
        assert len(candidates) == 0

    def test_fallback_when_too_few(self):
        """不足阈值时回退全量."""
        catalog = {
            "categories": {},
            "all_titles": {"A", "B", "C", "D", "E"},
        }
        # 仅 1 个候选但阈值默认 10 → 回退全量
        tokens = ["a"]
        candidates = catalog_filter(tokens, catalog, k=10)
        assert len(candidates) > 1
