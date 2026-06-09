# ============================================================================
# 检索引擎集中配置 — 所有可调参数
# ============================================================================

from dataclasses import dataclass, field


@dataclass
class RetrievalConfig:
    """检索流水线配置，支持环境变量覆盖。

    使用示例：
        from knowledge_wiki.wiki.retrieval.config import retrieval_config

        cfg = retrieval_config
        print(cfg.bm25_k1)  # 1.5
    """

    # ---- Feature flag ----
    # 总开关：False 时回退到旧 query_tool 实现
    enabled: bool = True

    # ---- Catalog 目录初筛 ----
    # 初筛后进入 BM25 的候选集大小（≤ 全量页数）
    catalog_top_k: int = 20
    # 初筛结果不足此数时回退全量（避免过严过滤）
    catalog_fallback_threshold: int = 10
    # 查询关键词 → (偏向类别, 加分值)
    catalog_category_boost: dict = field(default_factory=lambda: {
        "对比": ("综合分析", 2),
        "vs": ("综合分析", 2),
        "区别": ("综合分析", 2),
        "什么": ("概念", 1),
        "是什么": ("概念", 1),
        "定义": ("概念", 1),
    })

    # ---- BM25 ----
    # 词频饱和参数：值越大，词频出现多次的权重越大
    bm25_k1: float = 1.5
    # 长度归一化参数：值越大，长文档惩罚越强（0=不惩罚，1=强惩罚）
    bm25_b: float = 0.75
    # BM25 阶段取 Top-N 进入后续处理
    bm25_top_n: int = 10
    # 多字段权重：命中标题 > 命中标签 > 命中正文
    field_weights: dict = field(default_factory=lambda: {
        "title": 3.0,
        "tags": 2.0,
        "body": 1.0,
    })

    # ---- 分层组装 ----
    # 最终返回给 LLM 的结果数量
    final_top_n: int = 5
    # 总 token 预算（中英文混合，1 token ≈ 2 字符）
    token_budget_total: int = 8000
    # Layer 1: 编译真相（Top-1 frontmatter + 正文前 N 字）
    layer_1_budget: int = 1500
    layer_1_body_chars: int = 400
    # Layer 2: 交叉引用（Top-1 的 wikilink 邻居摘要）
    layer_2_budget: int = 1000
    # Layer 3: 证据补充（剩余 token 全部分给 Top-2..N 全文）

    # ---- 索引 ----
    # 增量更新阈值：累计变更 ≥ 此数时触发全量重建
    incremental_threshold: int = 5
    # 索引结构版本号（结构变更时递增）
    index_version: int = 1
    # 索引缓存目录（相对于 wiki_root）
    cache_dir: str = ".cache/retrieval"

    @property
    def layer_3_budget(self) -> int:
        """Layer 3 预算 = 余下的所有 token。"""
        return self.token_budget_total - self.layer_1_budget - self.layer_2_budget


# 全局单例
retrieval_config = RetrievalConfig()
