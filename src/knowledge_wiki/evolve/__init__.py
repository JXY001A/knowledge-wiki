"""自进化引擎 — Phase 5：知识缺口检测、Skill 效果追踪、定期自检报告.

模块:
    gap_detector.py — 从低分评估中识别知识盲区
    reporter.py     — 生成周度自检报告
"""

from knowledge_wiki.evolve.gap_detector import detect_gaps, generate_ingest_list
from knowledge_wiki.evolve.reporter import weekly_report, skill_stats

__all__ = ["detect_gaps", "generate_ingest_list", "weekly_report", "skill_stats"]
