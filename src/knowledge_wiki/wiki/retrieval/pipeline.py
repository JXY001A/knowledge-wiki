# ============================================================================
# 检索流水线编排 — catalog → bm25 → layered
# ============================================================================
# 端到端执行四阶段流水线：
#   Phase 0: 预处理（分词 + 去停用词）
#   Phase 1: Catalog 初筛（Wiki 目录.md 过滤候选）
#   Phase 2: BM25 排序（多字段加权打分）
#   Phase 3: 分层组装（Layer 1/2/3 结构化输出）
#
# 图谱加权（Phase 4）留待 200 页后实现。
# ============================================================================

import logging
from pathlib import Path
from time import time

from knowledge_wiki.config import settings
from knowledge_wiki.wiki.retrieval.bm25 import bm25_search, build_bm25_index
from knowledge_wiki.wiki.retrieval.catalog import catalog_filter, parse_catalog
from knowledge_wiki.wiki.retrieval.config import retrieval_config
from knowledge_wiki.wiki.retrieval.index_store import index_is_fresh, load_index, save_index
from knowledge_wiki.wiki.retrieval.layered import assemble_layered
from knowledge_wiki.wiki.retrieval.tokenizer import load_custom_dict, remove_stopwords, tokenize

_log = logging.getLogger(__name__)

# 模块初始化：加载自定义词典
try:
    load_custom_dict()
except Exception:
    _log.warning("无法加载自定义词典，分词可能不够精确", exc_info=True)


def _get_or_build_index() -> "BM25Index":
    """获取 BM25 索引（加载 → 校验 → 必要时重建）。

    Returns:
        可用的 BM25Index 实例
    """
    wiki_dir = settings.wiki_root / "wiki"

    # 尝试加载已有索引
    index = load_index()
    if index is not None and index_is_fresh(index, wiki_dir):
        return index

    # 重建索引
    _log.info("索引不存在或已过期，正在重建...")
    index = build_bm25_index(wiki_dir)
    save_index(index)
    _log.info("索引重建完成，共 %d 页", index.num_docs)
    return index


def run_pipeline(query: str, top_n: int | None = None) -> str:
    """端到端检索流水线。

    Args:
        query: 用户查询
        top_n: 最终返回结果数，默认 5

    Returns:
        分层结构化的 markdown 文本

    Raises:
        IndexNotReadyError: 索引未就绪（首次启动且 wiki 无 .md 文件时）
    """
    if top_n is None:
        top_n = retrieval_config.final_top_n

    cfg = retrieval_config
    t0 = time()
    timing: dict[str, float] = {}

    # ---- Phase 0：预处理 ----
    raw_tokens = tokenize(query, mode="search")
    tokens = remove_stopwords(raw_tokens)
    timing["preprocess"] = time() - t0

    # ---- Phase 1：Catalog 初筛 ----
    t1 = time()
    candidates = None  # None = 全量进 BM25
    try:
        catalog_index = parse_catalog()
        candidates = catalog_filter(tokens, catalog_index)
    except FileNotFoundError:
        _log.warning("Wiki 目录.md 不存在，跳过 Catalog 阶段，全量进 BM25")
    timing["catalog"] = time() - t1

    # ---- Phase 2：BM25 排序 ----
    t2 = time()
    index = _get_or_build_index()
    bm25_results = bm25_search(index, query, candidates=candidates, top_n=cfg.bm25_top_n)
    timing["bm25"] = time() - t2

    # ---- Phase 3：分层组装 ----
    t3 = time()
    layered_md = assemble_layered(query, bm25_results[:top_n])
    timing["layered"] = time() - t3

    # 日志（JSON 格式，方便 grep 和离线分析）
    timing["total"] = time() - t0
    _log.info(
        "检索完成 | query=%s | candidates=%s | bm25_top=%s | timing=%s",
        query,
        len(candidates) if candidates else "all",
        len(bm25_results),
        ", ".join(f"{k}={v * 1000:.0f}ms" for k, v in timing.items()),
    )

    return layered_md
