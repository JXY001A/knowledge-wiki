"""Wiki 搜索 — 关键字匹配、页面列举、Wikilink 提取."""

import re
from pathlib import Path
from knowledge_wiki.config import settings
from knowledge_wiki.wiki.frontmatter import parse_frontmatter


def list_wiki_pages() -> list[dict]:
    """列出所有 wiki 页面及其 frontmatter 元数据."""
    pages = []
    wiki_d = settings.wiki_root / "wiki"
    if not wiki_d.exists():
        return pages
    for md in sorted(wiki_d.rglob("*.md")):
        fm = parse_frontmatter(md)
        pages.append({
            "path": str(md.relative_to(settings.wiki_root)),
            "title": fm.get("title", md.stem) if fm else md.stem,
            "type": fm.get("type", "unknown") if fm else "unknown",
            "tags": fm.get("tags", []) if fm else [],
            "updated": fm.get("updated", "") if fm else "",
            "confidence": fm.get("confidence", "") if fm else "",
            "size_lines": len(md.read_text().splitlines()),
        })
    return pages


def search_wiki(keyword: str, max_results: int = 10) -> list[dict]:
    """在 wiki/ 中按关键词搜索，返回匹配页面及摘录."""
    results = []
    wiki_d = settings.wiki_root / "wiki"
    if not wiki_d.exists():
        return results

    for md in sorted(wiki_d.rglob("*.md")):
        text = md.read_text()
        if keyword.lower() in text.lower():
            lines = text.splitlines()
            excerpt = ""
            for i, line in enumerate(lines):
                if keyword.lower() in line.lower():
                    start = max(0, i - 1)
                    end = min(len(lines), i + 2)
                    excerpt = "\n".join(lines[start:end])
                    break
            results.append({
                "path": str(md.relative_to(settings.wiki_root)),
                "title": md.stem,
                "excerpt": excerpt[:300],
            })
        if len(results) >= max_results:
            break
    return results


def keyword_search(query: str, max_results: int = 10) -> list[tuple[int, str, Path]]:
    """关键字权重搜索 — 路径匹配权重 ×2，正文匹配 ×1.

    Returns: [(score, page_title, file_path), ...] 按分数降序
    """
    wiki_d = settings.wiki_root / "wiki"
    if not wiki_d.exists():
        return []

    keywords = query.lower().split()
    results = []
    for md in sorted(wiki_d.rglob("*.md")):
        text = md.read_text()
        score = sum(1 for kw in keywords if kw in text.lower())
        score += sum(2 for kw in keywords if kw in str(md).lower())

        if score > 0:
            title = md.stem
            fm = parse_frontmatter(md)
            if fm and fm.get("title"):
                title = fm["title"]
            results.append((score, title, md))

    results.sort(key=lambda x: x[0], reverse=True)
    return results[:max_results]


def get_top_page_titles(query: str) -> str:
    """获取与查询相关度最高的页面标题，用于引用."""
    results = keyword_search(query, max_results=5)
    if results:
        return ", ".join(title for _, title, _ in results)
    return "知识库"


def extract_wikilinks(text: str) -> list[str]:
    """提取文本中所有 [[wikilink]] 目标."""
    return re.findall(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]", text)


def get_all_page_titles() -> set[str]:
    """返回所有 wiki 页面的 stem 名称集合."""
    wiki_d = settings.wiki_root / "wiki"
    if not wiki_d.exists():
        return set()
    return {md.stem for md in wiki_d.rglob("*.md")}
