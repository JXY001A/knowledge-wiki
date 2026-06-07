"""自动摄取 — 缺口 → 搜索 → 建议 → 摄入.

流程：
    1. detect_gaps() → 提取高频缺口主题
    2. search_gap_topics() → DuckDuckGo 搜索相关文章 URL
    3. suggest_ingest() → 生成建议清单供用户确认
    4. auto_ingest() → 下载 + 分析 + 创建 wiki 页面
"""

import json
import logging
import re
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from knowledge_wiki.config import settings

_log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果."""
    title: str = ""
    url: str = ""
    snippet: str = ""
    topic: str = ""  # 对应的缺口主题


def search_gap_topics(topics: list[str], max_per_topic: int = 3) -> list[SearchResult]:
    """为每个缺口主题搜索相关文章 URL.

    使用 DuckDuckGo Lite（无需 API key）。

    Args:
        topics: 缺口主题列表
        max_per_topic: 每个主题最多返回 N 条结果

    Returns:
        SearchResult 列表
    """
    all_results = []

    for topic in topics[:5]:  # 最多搜索 5 个主题
        results = _search_ddg(topic, max_per_topic)
        for r in results:
            r.topic = topic
        all_results.extend(results)

    return all_results


def _search_ddg(query: str, max_results: int = 3) -> list[SearchResult]:
    """DuckDuckGo Lite 搜索.

    Args:
        query: 搜索词
        max_results: 最大结果数

    Returns:
        SearchResult 列表
    """
    results = []
    try:
        params = urllib.parse.urlencode({"q": query, "kl": "cn-zh"})
        url = f"https://lite.duckduckgo.com/lite/?{params}"

        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; KnowledgeBot/1.0)",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 解析 DDG Lite 结果
        # 格式: <a rel="nofollow" href="URL">Title</a><span>Snippet</span>
        links = re.findall(
            r'<a[^>]*href="(https?://[^"]+)"[^>]*>([^<]+)</a>\s*<span[^>]*>([^<]*)',
            html, re.DOTALL,
        )

        for url, title, snippet in links[:max_results]:
            title = re.sub(r"<[^>]+>", "", title).strip()
            snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            if title and url and "duckduckgo" not in url:
                results.append(SearchResult(
                    title=title[:100],
                    url=url,
                    snippet=snippet[:200],
                ))

    except Exception as e:
        _log.warning("搜索 %s 失败: %s", query, e)

    return results


def suggest_ingest() -> dict:
    """生成自动摄取建议.

    从最新评估缺口出发，生成搜索链接。

    Returns:
        {"gaps": [...], "suggestions": [SearchResult], "message": "..."}
    """
    from knowledge_wiki.evolve.gap_detector import detect_gaps

    # 从评估记录中提取真实缺口
    raw_gaps = detect_gaps(min_score=5)
    topics = []
    seen = set()
    for g in raw_gaps:
        for gap_item in g.get("gaps", []):
            if gap_item not in seen and len(gap_item) > 2:
                topics.append(gap_item)
                seen.add(gap_item)

    if not topics:
        return {"gaps": [], "suggestions": [], "message": "未检测到知识缺口。"}

    # 生成 Bing 搜索链接（国内可访问）
    suggestions = []
    for topic in topics[:5]:
        encoded = urllib.parse.quote(topic)
        suggestions.append(SearchResult(
            title=f"搜索：{topic}",
            url=f"https://www.bing.com/search?q={encoded}",
            snippet="点击链接搜索相关文章",
            topic=topic,
        ))

    return {
        "gaps": [{"topic": t, "count": 1} for t in topics[:10]],
        "suggestions": suggestions,
        "message": f"检测到 {len(topics)} 个知识缺口，生成 {len(suggestions)} 个搜索链接。",
    }


def auto_ingest_topic(topic: str, url: str) -> str:
    """下载文章并自动摄取到 wiki.

    复用现有 ingest 管线：下载 → DeepSeek 分析 → wiki 页面。

    Args:
        topic: 缺口主题
        url: 文章 URL

    Returns:
        摄取结果描述
    """
    # 复用 webhook 的 URL ingest 流程
    from knowledge_wiki.webhook.process import fetch_url_text
    from knowledge_wiki.llm.deepseek import call_ingest
    from knowledge_wiki.wiki.builder import build_source_page, build_concept_page, extract_concept_names
    from knowledge_wiki.wiki.log import append_ingest_log
    from knowledge_wiki.wiki.git import commit_and_push

    # 下载
    raw_text = fetch_url_text(url)
    if not raw_text:
        return f"无法下载 {url}"

    # DeepSeek 分析
    llm_data = call_ingest(raw_text, url)
    if not llm_data:
        return f"LLM 分析失败: {url}"

    # 构建 wiki 页面
    wiki_file = build_source_page(llm_data, url)
    new_pages = []
    for c in llm_data.get("concepts", []):
        cp = build_concept_page(c)
        if cp:
            new_pages.append(cp)

    page_title = llm_data.get("title", wiki_file.stem)
    append_ingest_log(llm_data, url, page_title)
    commit_and_push(f"auto-ingest: {page_title} (gap: {topic})")

    concepts = extract_concept_names(llm_data.get("concepts", []))
    result = f"✅ 已自动摄取：**{page_title}**\n领域：{llm_data.get('domain', '未知')}"
    if concepts:
        result += f"\n新概念：{', '.join(concepts)}"

    return result


def suggest_markdown() -> str:
    """生成摄取建议的 markdown 文本（用于企微推送）.

    Returns:
        markdown 格式的建议
    """
    data = suggest_ingest()
    suggestions = data.get("suggestions", [])

    if not suggestions:
        return "✅ 当前未检测到需要自动摄取的知识缺口。"

    lines = [
        f"## 🔍 知识缺口 + 搜索建议",
        f"",
        f"检测到以下知识缺口，点击链接搜索相关文章：",
        f"",
    ]

    for i, s in enumerate(suggestions[:8], 1):
        lines.append(f"{i}. [{s.topic}]({s.url})")

    lines.append("")
    lines.append("找到文章后可回复 `摄取 <URL>` 自动摄入。")

    return "\n".join(lines)
