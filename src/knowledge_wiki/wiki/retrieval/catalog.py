# ============================================================================
# Catalog 目录优先层 — 解析 Wiki 目录.md 做廉价初筛
# ============================================================================
# Wiki 目录.md 是 LLM 自维护的轻量 sitemap，按"领域 + 概念 + 综合分析"等
# 类别组织所有页面。本模块解析该文件，对查询做：
#   1. 关键词命中标题 → 算分
#   2. 查询意图 → 类别 boost（如"对比"→偏向"综合分析"）
#   3. 取 Top-K 候选（K=20），不足时回退全量
#
# 性能：~5ms，远快于全量扫描 frontmatter。
# ============================================================================

import re
from pathlib import Path

from knowledge_wiki.config import settings
from knowledge_wiki.wiki.retrieval.config import retrieval_config

# 解析正则
# H2 — 大类（如 "## 领域页"）
RE_H2 = re.compile(r"^##\s+(.+)$")
# H3 — 子类（如 "### AI平台"）
RE_H3 = re.compile(r"^###\s+(.+)$")
# wikilink 项 — 如 "- [[DeepSeek]]"
RE_LINK = re.compile(r"^-\s+\[\[([^\]]+)\]\]")


def parse_catalog(catalog_path: Path | None = None):
    """解析 Wiki 目录.md，构建内存索引。

    Args:
        catalog_path: 目录文件路径，默认 wiki/Wiki 目录.md

    Returns:
        dict 结构:
        {
            "categories": {"大类": ["页面1", "页面2", ...], ...},
            "all_titles": {"页面1", "页面2", ...},
        }

    Raises:
        FileNotFoundError: 目录文件不存在（调用方应降级到全量）
    """
    if catalog_path is None:
        catalog_path = settings.wiki_root / "wiki" / "Wiki 目录.md"

    if not catalog_path.exists():
        raise FileNotFoundError(f"目录文件不存在: {catalog_path}")

    text = catalog_path.read_text(encoding="utf-8")

    categories: dict[str, list[str]] = {}
    all_titles: set[str] = set()

    current_h2: str | None = None
    current_h3: str | None = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # 匹配 H2 大类
        h2_match = RE_H2.match(line)
        if h2_match:
            current_h2 = h2_match.group(1).strip()
            if current_h2 not in categories:
                categories[current_h2] = []
            continue

        # 匹配 H3 子类
        h3_match = RE_H3.match(line)
        if h3_match:
            current_h3 = h3_match.group(1).strip()
            if current_h3 not in categories:
                categories[current_h3] = []
            continue

        # 匹配 wikilink 项
        link_match = RE_LINK.match(line)
        if link_match:
            title = link_match.group(1).strip()
            all_titles.add(title)

            # 归到最近的 H3 或 H2
            category = current_h3 or current_h2
            if category and title not in categories.get(category, []):
                categories[category].append(title)
            continue

    return {
        "categories": categories,
        "all_titles": all_titles,
    }


def catalog_filter(
    query_tokens: list[str],
    catalog_index: dict,
    k: int | None = None,
) -> list[str]:
    """按查询 token 命中和类别意图做初筛。

    Args:
        query_tokens: 查询分词（已去停用词）
        catalog_index: parse_catalog 的返回值
        k: 返回候选集大小，默认 20

    Returns:
        候选页面标题列表（≤ k）
    """
    if k is None:
        k = retrieval_config.catalog_top_k

    cfg = retrieval_config
    all_titles = catalog_index["all_titles"]
    categories = catalog_index["categories"]

    # 查询意图 → 类别 boost
    query_text = "".join(query_tokens).lower()
    intent_boost: dict[str, int] = {}
    for keyword, (category, boost) in cfg.catalog_category_boost.items():
        if keyword in query_text:
            intent_boost[category] = intent_boost.get(category, 0) + boost

    # 遍历所有标题打分
    scored: list[tuple[int, str]] = []
    for title in all_titles:
        title_lower = title.lower()
        # 命中分：每个 token 在标题中出现则 +1
        hit_score = sum(1 for tok in query_tokens if tok.lower() in title_lower)
        if hit_score == 0:
            continue

        # 类别 boost：标题属于哪个类别
        boost = 0
        for cat, cat_boost in intent_boost.items():
            if title in categories.get(cat, []):
                boost += cat_boost

        scored.append((hit_score + boost, title))

    # 按分降序，取 Top-K
    scored.sort(key=lambda x: x[0], reverse=True)
    candidates = [title for _, title in scored[:k]]

    # 回退：结果太少则返回全量
    threshold = retrieval_config.catalog_fallback_threshold
    if len(candidates) < threshold:
        candidates = list(all_titles)

    return candidates[:k]
