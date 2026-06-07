"""自进化引擎 — Phase 5：知识缺口检测、Skill 效果追踪、定期自检报告、自动摄取.

模块:
    gap_detector.py — 从低分评估中识别知识盲区
    reporter.py     — 生成周度自检报告
    auto_ingest.py  — 缺口 → 搜索 → 建议 → 自动摄入
"""

from knowledge_wiki.evolve.gap_detector import detect_gaps, generate_ingest_list
from knowledge_wiki.evolve.reporter import weekly_report, skill_stats
from knowledge_wiki.evolve.auto_ingest import suggest_ingest, auto_ingest_topic, search_gap_topics, suggest_markdown

__all__ = [
    "detect_gaps", "generate_ingest_list",
    "weekly_report", "skill_stats",
    "suggest_ingest", "auto_ingest_topic", "search_gap_topics", "suggest_markdown",
]
