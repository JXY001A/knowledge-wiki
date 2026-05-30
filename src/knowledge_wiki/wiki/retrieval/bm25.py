# ============================================================================
# BM25 检索引擎 — Okapi BM25 多字段加权
# ============================================================================
# 把 wiki 页面拆为 title/tags/body 三个字段，分别建 BM25 索引后加权求和：
#   final_score = w_title × BM25(title) + w_tags × BM25(tags) + w_body × BM25(body)
#
# 依赖 rank-bm25 库实现 Okapi BM25 公式。
# ============================================================================

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from knowledge_wiki.config import settings
from knowledge_wiki.wiki.frontmatter import parse_frontmatter
from knowledge_wiki.wiki.retrieval.config import retrieval_config
from knowledge_wiki.wiki.retrieval.tokenizer import tokenize

if TYPE_CHECKING:
    from rank_bm25 import BM25Okapi


@dataclass
class DocMeta:
    """单个 wiki 页面的元数据（随索引持久化）。"""

    doc_id: int
    path: str  # 相对 wiki_root 的路径，如 "wiki/概念/DeepSeek.md"
    title: str
    type: str  # entity/concept/topic/comparison/source/synthesis
    tags: list[str]
    confidence: str  # high/medium/low
    updated: str  # frontmatter 中的 updated 字段
    sha256: str  # 文件内容 hash，用于增量判断


@dataclass
class BM25Result:
    """单次 BM25 查询的某一条结果。"""

    doc_id: int
    title: str
    path: str
    score: float  # 加权总分
    field_scores: dict[str, float]  # 各字段分数（调试用）: {"title": 1.2, ...}
    final_score: float = 0.0  # 经图谱加权后的最终分（由 boost 模块设置）


@dataclass
class BM25Index:
    """BM25 索引实体（可序列化）。"""

    version: int  # 索引结构版本
    built_at: datetime  # 构建时间
    num_docs: int  # 已索引文档数
    avgdl: dict[str, float]  # 各字段平均文档长度

    # 三个独立 BM25 实例（不可直接序列化，由 index_store 处理）
    title_bm25: "BM25Okapi"
    tags_bm25: "BM25Okapi"
    body_bm25: "BM25Okapi"

    # 文档 ID → 元数据映射
    doc_meta: dict[int, DocMeta] = field(default_factory=dict)
    # 标题 → 文档 ID 反向映射
    title_to_id: dict[str, int] = field(default_factory=dict)

    # 分词后的 token 列表（保留供调试与重建）
    title_tokens: list[list[str]] = field(default_factory=list)
    tags_tokens: list[list[str]] = field(default_factory=list)
    body_tokens: list[list[str]] = field(default_factory=list)


def build_bm25_index(wiki_dir: Path | None = None) -> BM25Index:
    """扫描 wiki/ 下所有 .md 文件，构建多字段 BM25 索引。

    Args:
        wiki_dir: wiki 根目录，默认使用 settings.wiki_root / "wiki"

    Returns:
        完整的多字段 BM25Index

    排除文件：
        - Wiki 目录.md（目录页，非内容页）
        - 操作日志.md（日志页，非内容页）
        - hot*.md（热更新页）
    """
    from hashlib import sha256
    from rank_bm25 import BM25Okapi

    if wiki_dir is None:
        wiki_dir = settings.wiki_root / "wiki"

    cfg = retrieval_config
    exclude_stems = {"wiki 目录", "wiki目录", "操作日志"}

    # Phase 1：扫描并收集文档
    title_texts: list[str] = []
    tags_texts: list[str] = []
    body_texts: list[str] = []
    meta_list: list[DocMeta] = []

    doc_idx = 0  # 独立计数器，不受排除文件影响
    for md_path in sorted(wiki_dir.rglob("*.md")):
        # 排除特殊页
        if md_path.stem.lower() in exclude_stems or md_path.name.startswith("hot"):
            continue

        text = md_path.read_text(encoding="utf-8")
        content_hash = sha256(text.encode("utf-8")).hexdigest()

        # 解析 frontmatter
        fm = parse_frontmatter(md_path)
        if fm:
            page_title = fm.get("title", md_path.stem)
            page_type = fm.get("type", "unknown")
            page_tags = fm.get("tags", [])
            page_conf = fm.get("confidence", "")
            page_updated = fm.get("updated", "")
            # 正文 = 去掉 frontmatter 后的内容
            body = text.split("---\n", 2)[-1] if text.startswith("---") else text
        else:
            page_title = md_path.stem
            page_type = "unknown"
            page_tags = []
            page_conf = ""
            page_updated = ""
            body = text

        # 字段分词（index 模式：粗粒度，保留语义单元）
        title_tokens = tokenize(page_title, mode="index")
        tags_str = " ".join(page_tags) if page_tags else ""
        tags_tokens = tokenize(tags_str, mode="index") if tags_str else []
        body_tokens = tokenize(body, mode="index")

        title_texts.append(page_title)
        tags_texts.append(tags_str)
        body_texts.append(body)

        # 记录元数据
        meta = DocMeta(
            doc_id=doc_idx,
            path=str(md_path.relative_to(settings.wiki_root)),
            title=page_title,
            type=page_type,
            tags=list(page_tags) if isinstance(page_tags, list) else [page_tags],
            confidence=page_conf,
            updated=page_updated,
            sha256=content_hash,
        )
        meta_list.append(meta)
        doc_idx += 1

    n = len(meta_list)

    # Phase 2：构建三个 BM25Okapi 实例
    # rank-bm25 库接受 list[list[str]] 作为输入，内部按空格拼接
    title_tokens_list = [tokenize(t, mode="index") for t in title_texts]
    tags_tokens_list = [tokenize(t, mode="index") for t in tags_texts]
    body_tokens_list = [tokenize(t, mode="index") for t in body_texts]

    # 计算各字段平均长度
    avg_title_len = sum(len(t) for t in title_tokens_list) / max(n, 1)
    avg_tags_len = sum(len(t) for t in tags_tokens_list) / max(n, 1)
    avg_body_len = sum(len(t) for t in body_tokens_list) / max(n, 1)

    # 构建 BM25 实例
    title_bm25 = BM25Okapi(title_tokens_list, k1=cfg.bm25_k1, b=cfg.bm25_b)
    tags_bm25 = BM25Okapi(tags_tokens_list, k1=cfg.bm25_k1, b=cfg.bm25_b)
    body_bm25 = BM25Okapi(body_tokens_list, k1=cfg.bm25_k1, b=cfg.bm25_b)

    # Phase 3：组装索引对象
    index = BM25Index(
        version=cfg.index_version,
        built_at=datetime.now(timezone.utc),
        num_docs=n,
        avgdl={
            "title": avg_title_len,
            "tags": avg_tags_len,
            "body": avg_body_len,
        },
        title_bm25=title_bm25,
        tags_bm25=tags_bm25,
        body_bm25=body_bm25,
        doc_meta={m.doc_id: m for m in meta_list},
        title_to_id={m.title: m.doc_id for m in meta_list},
        title_tokens=title_tokens_list,
        tags_tokens=tags_tokens_list,
        body_tokens=body_tokens_list,
    )
    return index


def bm25_search(
    index: BM25Index,
    query: str,
    candidates: list[str] | None = None,
    top_n: int | None = None,
) -> list[BM25Result]:
    """多字段 BM25 查询。

    Args:
        index: BM25 索引
        query: 查询字符串
        candidates: 候选页面标题列表（来自 catalog 初筛），None 时全量打分
        top_n: 返回结果数，默认使用配置值

    Returns:
        按加权分数降序的结果列表
    """
    import math

    if top_n is None:
        top_n = retrieval_config.bm25_top_n

    cfg = retrieval_config
    w_title, w_tags, w_body = (
        cfg.field_weights["title"],
        cfg.field_weights["tags"],
        cfg.field_weights["body"],
    )

    num_docs = index.num_docs

    # 生成查询分词（search 模式：细粒度，提高召回）
    query_tokens = tokenize(query, mode="search")

    # 计算候选集 ID 范围
    if candidates:
        # 将候选标题映射为 doc_id，没在索引中的跳过
        candidate_ids = {
            index.title_to_id[t]
            for t in candidates
            if t in index.title_to_id
        }
        candidate_ids_list = list(candidate_ids)
    else:
        candidate_ids_list = list(range(num_docs))

    results = []
    for doc_id in candidate_ids_list:
        # 归一化：BM25Okapi.get_scores 返回原始分数，
        # 各字段量纲不同，用加法合并即可（权重已通过 w_* 控制）
        t_score = _get_single_score(index.title_bm25, query_tokens, doc_id)
        a_score = _get_single_score(index.tags_bm25, query_tokens, doc_id)
        b_score = _get_single_score(index.body_bm25, query_tokens, doc_id)

        # 加权求和
        weighted_score = w_title * t_score + w_tags * a_score + w_body * b_score

        if weighted_score > 0:
            meta = index.doc_meta[doc_id]
            results.append(BM25Result(
                doc_id=doc_id,
                title=meta.title,
                path=meta.path,
                score=weighted_score,
                field_scores={"title": t_score, "tags": a_score, "body": b_score},
            ))

    # 按加权分数降序，取 top_n
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_n]


def _get_single_score(bm25, query_tokens: list[str], doc_id: int) -> float:
    """获取单个文档在某个字段上的 BM25 分数。

    解决 rank-bm25 库的单字段打分。

    Args:
        bm25: 某字段的 BM25Okapi 实例
        query_tokens: 查询分词
        doc_id: 文档索引 ID

    Returns:
        该字段的 BM25 分数
    """
    scores = bm25.get_scores(query_tokens)
    return float(scores[doc_id])
