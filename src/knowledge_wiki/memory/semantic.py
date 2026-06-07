"""语义记忆增强 — 概念覆盖度分析与关联图自动化.

与现有 lint 工具互补：
    - lint.py: 格式检查（死链、孤页、标签缺失）
    - semantic.py: 语义检查（概念覆盖度、领域空白、关联密度）
"""

import logging
from collections import Counter
from pathlib import Path
from knowledge_wiki.config import settings
from knowledge_wiki.wiki.frontmatter import parse_frontmatter
from knowledge_wiki.wiki.search import list_wiki_pages

_log = logging.getLogger(__name__)

WIKI_ROOT = settings.wiki_root


def concept_coverage() -> dict:
    """分析 wiki/概念/ 的覆盖度.

    Returns:
        覆盖度分析结果字典
    """
    pages = list_wiki_pages()

    # 概念页 vs 非概念页
    concept_pages = [p for p in pages if p["type"] == "concept"]
    source_pages = [p for p in pages if p["type"] == "source"]
    synthesis_pages = [p for p in pages if p["type"] == "synthesis"]
    topic_pages = [p for p in pages if p["type"] == "topic"]

    # 所有其他页面中引用的概念（通过 wikilinks）
    from knowledge_wiki.wiki.search import extract_wikilinks

    all_referenced = Counter()
    for p in pages:
        filepath = WIKI_ROOT / p["path"]
        if filepath.exists():
            links = extract_wikilinks(filepath.read_text(encoding="utf-8"))
            for link in links:
                all_referenced[link] += 1

    # 查找被多次引用但没有独立概念页的概念
    existing_concepts = {p["title"] for p in concept_pages}
    missing_concepts = []
    for title, count in all_referenced.most_common(30):
        if title not in existing_concepts and count >= 2:
            missing_concepts.append({"title": title, "references": count})

    # 领域覆盖
    domains = Counter()
    for p in source_pages:
        # 从 tags 推断领域
        for tag in p.get("tags", []):
            if tag not in ("概念", "教程", "深度", "综述", "观点", "资讯", "工具",
                           "范式", "反模式", "案例", "基准", "最佳实践",
                           "长青", "易过时", "基础", "进阶"):
                domains[tag] += 1

    # 概念关联密度
    concept_links = 0
    for p in concept_pages:
        filepath = WIKI_ROOT / p["path"]
        if filepath.exists():
            links = extract_wikilinks(filepath.read_text(encoding="utf-8"))
            concept_links += len([l for l in links if l in existing_concepts])

    avg_links = concept_links / len(concept_pages) if concept_pages else 0

    return {
        "total_pages": len(pages),
        "concept_pages": len(concept_pages),
        "source_pages": len(source_pages),
        "synthesis_pages": len(synthesis_pages),
        "topic_pages": len(topic_pages),
        "missing_concepts": missing_concepts[:10],
        "top_domains": domains.most_common(8),
        "concept_link_density": round(avg_links, 1),
        "orphan_count": sum(1 for p in concept_pages if all_referenced.get(p["title"], 0) == 0),
    }


def concept_coverage_report() -> str:
    """生成概念覆盖度报告（markdown）.

    Returns:
        markdown 格式的报告
    """
    data = concept_coverage()

    lines = [
        "## 概念覆盖度报告",
        "",
        f"| 指标 | 值 |",
        f"|------|----|",
        f"| 总页面数 | {data['total_pages']} |",
        f"| 概念页 | {data['concept_pages']} |",
        f"| 资料摘要 | {data['source_pages']} |",
        f"| 综合分析 | {data['synthesis_pages']} |",
        f"| 概念关联密度 | {data['concept_link_density']}（平均每概念 {data['concept_link_density']} 条链接） |",
        f"| 孤立概念 | {data['orphan_count']}（无其他页面引用） |",
    ]

    # 缺失概念
    missing = data.get("missing_concepts", [])
    if missing:
        lines.append("")
        lines.append("### ⚠️ 缺少独立页面的概念（被多次引用）")
        lines.append("")
        lines.append("| 概念 | 被引用次数 |")
        lines.append("|------|-----------|")
        for m in missing:
            lines.append(f"| [[{m['title']}]] | {m['references']} |")
    else:
        lines.append("")
        lines.append("### ✅ 所有活跃概念均有独立页面")

    # 领域分布
    domains = data.get("top_domains", [])
    if domains:
        lines.append("")
        lines.append("### 资料摘要领域分布")
        lines.append("")
        lines.append("| 领域 | 数量 |")
        lines.append("|------|------|")
        for d, c in domains:
            lines.append(f"| {d} | {c} |")

    return "\n".join(lines)
