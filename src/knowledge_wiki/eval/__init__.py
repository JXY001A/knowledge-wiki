"""评估系统 — Phase 4：回答质量评分、知识覆盖分析、反馈收集.

模块:
    scorer.py  — DeepSeek API 评分引擎
"""

from knowledge_wiki.eval.scorer import evaluate_answer, EvalResult

__all__ = ["evaluate_answer", "EvalResult"]
