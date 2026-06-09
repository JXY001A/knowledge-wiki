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


# ============================================================================
# 闭环自动摄取引擎
# ============================================================================

# 安全阈值
MAX_AUTO_INGEST_PER_WEEK = 5
AUTO_INGEST_TRACKER_FILE = settings.wiki_root / "wiki" / ".data" / "auto_ingest_log.json"


def _load_auto_ingest_log() -> dict:
    """加载自动摄取日志（跟踪每周摄取次数）."""
    import json
    if AUTO_INGEST_TRACKER_FILE.exists():
        try:
            return json.loads(AUTO_INGEST_TRACKER_FILE.read_text())
        except Exception:
            pass
    return {"week_start": "", "count": 0, "ingested": []}


def _save_auto_ingest_log(log: dict) -> None:
    """保存自动摄取日志."""
    import json
    AUTO_INGEST_TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTO_INGEST_TRACKER_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2))


def _reset_weekly_counter(log: dict) -> dict:
    """重置每周计数器（新的一周）."""
    from datetime import datetime, timedelta
    today = datetime.now().date()
    # 周一作为新周开始
    monday = (today - timedelta(days=today.weekday())).isoformat()
    if log.get("week_start") != monday:
        log["week_start"] = monday
        log["count"] = 0
    return log


def run_auto_ingest_cycle(dry_run: bool = False) -> dict:
    """执行一次闭环自动摄取周期.

    流程：
    1. 检测反复出现的知识缺口（出现 3+ 次）
    2. 搜索相关文章
    3. 自动摄取（安全阈值内）
    4. 推送通知

    Args:
        dry_run: True 时只返回计划，不执行实际摄取

    Returns:
        {"ingested": [...], "skipped": [...], "message": "..."}
    """
    from knowledge_wiki.evolve.gap_detector import get_recurring_gaps

    # 1. 检测反复缺口
    recurring = get_recurring_gaps(min_occurrences=3, days=30)
    if not recurring:
        return {"ingested": [], "skipped": [], "message": "未发现反复出现的知识缺口。"}

    # 2. 加载周计数
    log = _reset_weekly_counter(_load_auto_ingest_log())
    remaining = MAX_AUTO_INGEST_PER_WEEK - log["count"]

    result = {"ingested": [], "skipped": [], "message": ""}

    if remaining <= 0:
        result["message"] = f"本周自动摄取已达上限（{MAX_AUTO_INGEST_PER_WEEK} 篇），以下缺口将转为建议："
        for g in recurring[:5]:
            result["skipped"].append({"topic": g["topic"], "count": g["count"]})
        return result

    # 3. 逐个处理缺口
    for gap in recurring[:remaining]:
        topic = gap["topic"]
        _log.info("自动摄取缺口: %s (出现 %d 次)", topic, gap["count"])

        if dry_run:
            result["ingested"].append({"topic": topic, "status": "dry_run"})
            continue

        # 搜索文章
        search_results = search_gap_topics([topic], max_per_topic=2)
        if not search_results:
            result["skipped"].append({"topic": topic, "reason": "搜索无结果"})
            continue

        # 尝试摄取第一个 URL
        ingested = False
        for sr in search_results:
            if not sr.url:
                continue
            ingest_result = auto_ingest_topic(topic, sr.url)
            if "✅" in ingest_result:
                log["count"] += 1
                from datetime import datetime as dt_now
                log["ingested"].append({
                    "topic": topic,
                    "url": sr.url,
                    "result": ingest_result,
                    "time": dt_now.now().isoformat(),
                })
                result["ingested"].append({"topic": topic, "url": sr.url, "result": ingest_result})
                ingested = True
                break
            else:
                _log.warning("摄取失败: %s → %s", topic, ingest_result)

        if not ingested:
            result["skipped"].append({"topic": topic, "reason": "所有 URL 摄取失败"})

    _save_auto_ingest_log(log)

    # 4. 生成摘要消息
    parts = []
    if result["ingested"]:
        parts.append(f"✅ 自动摄取 {len(result['ingested'])} 篇：")
        for item in result["ingested"]:
            parts.append(f"  - {item.get('topic', '?')}")
    if result["skipped"]:
        parts.append(f"⏭️ 跳过 {len(result['skipped'])} 个缺口：")
        for item in result["skipped"][:3]:
            parts.append(f"  - {item.get('topic', '?')}（{item.get('reason', '?')}）")
    result["message"] = "\n".join(parts) if parts else "无操作"

    return result


def auto_ingest_scheduled() -> str:
    """定时调用的自动摄取入口（每周日 10:00 触发，scheduler 已集成）.

    Returns:
        推送消息文本
    """
    result = run_auto_ingest_cycle(dry_run=False)

    if not result["ingested"] and not result["skipped"]:
        return result.get("message", "")

    lines = ["## 🤖 自动知识补充报告", ""]
    if result["ingested"]:
        lines.append(f"### ✅ 已自动摄入（{len(result['ingested'])} 篇）")
        for item in result["ingested"]:
            lines.append(f"- {item.get('topic', '?')}")
        lines.append("")
    if result["skipped"]:
        lines.append(f"### ⏭️ 跳过（{len(result['skipped'])} 个）")
        for item in result["skipped"][:5]:
            lines.append(f"- {item.get('topic', '?')}：{item.get('reason', '建议手动处理')}")
        lines.append("")
    lines.append("回复「摄取建议」查看完整列表。")

    return "\n".join(lines)
