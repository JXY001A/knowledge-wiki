# ============================================================================
# 结果融合 — RRF (Reciprocal Rank Fusion) 合并双路检索结果
# ============================================================================
# 将 BM25（关键词匹配）和 Embedding（语义匹配）的结果按 RRF 算法合并，
# 取两路各自的 Top-K，加权融合排序，去重后输出 Top-N。
#
# RRF 公式: score(d) = Σ 1/(k + rank_i(d))
#   k = 60（默认，平滑参数）
#   结果按 score 降序，分数越高表示在越多通路中排名越靠前。
# ============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FusedResult:
    """融合后的单条结果."""

    title: str
    path: str
    score: float  # RRF 融合分数
    bm25_score: float = 0.0  # 原始 BM25 分数
    embed_score: float = 0.0  # 原始语义相似度
    sources: list[str] = field(default_factory=list)  # ["bm25", "embedding"]


def rrf_fusion(
    bm25_results: list[tuple[str, str, float]],  # [(title, path, score), ...]
    embed_results: list[tuple[str, str, float]],  # [(path, title, score), ...]
    k: int = 60,
    top_n: int = 10,
    bm25_weight: float = 1.0,
    embed_weight: float = 1.0,
) -> list[FusedResult]:
    """RRF 双路融合。

    对 BM25 和 Embedding 各自排名，按 1/(k + rank) 加权求和，
    去重后取 top_n。

    Args:
        bm25_results: BM25 结果 [(title, path, bm25_score), ...]
        embed_results: Embedding 结果 [(path, title, cosine_sim), ...]
        k: RRF 平滑参数（默认 60）
        top_n: 最终返回结果数
        bm25_weight: BM25 通路权重
        embed_weight: Embedding 通路权重

    Returns:
        按 RRF 分数降序的融合结果列表
    """
    # 为每个文档计算 RRF 分数
    # key = 路径（路径在两路中一致，作为去重键）
    rrf_scores: dict[str, float] = {}
    bm25_scores: dict[str, float] = {}
    embed_scores: dict[str, float] = {}
    titles: dict[str, str] = {}
    sources: dict[str, list[str]] = {}

    # BM25 贡献
    for rank, (title, path, score) in enumerate(bm25_results, 1):
        rrf = bm25_weight / (k + rank)
        rrf_scores[path] = rrf_scores.get(path, 0.0) + rrf
        bm25_scores[path] = score
        titles[path] = title
        sources.setdefault(path, []).append("bm25")

    # Embedding 贡献
    # embed_results 格式: [(path, title, cosine_sim), ...]
    for rank, (path, title, score) in enumerate(embed_results, 1):
        rrf = embed_weight / (k + rank)
        rrf_scores[path] = rrf_scores.get(path, 0.0) + rrf
        embed_scores[path] = score
        if path not in titles:
            titles[path] = title
        sources.setdefault(path, []).append("embedding")

    # 组装结果
    fused = []
    for path, rrf_score in rrf_scores.items():
        fused.append(FusedResult(
            title=titles.get(path, Path(path).stem),
            path=path,
            score=rrf_score,
            bm25_score=bm25_scores.get(path, 0.0),
            embed_score=embed_scores.get(path, 0.0),
            sources=sources.get(path, ["unknown"]),
        ))

    # 按 RRF 分数降序
    fused.sort(key=lambda r: -r.score)
    return fused[:top_n]
