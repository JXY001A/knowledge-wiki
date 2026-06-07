"""MCP lint 工具 — wiki 健康检查."""

from datetime import datetime, timezone
from knowledge_wiki.config import settings
from knowledge_wiki.wiki.git import pull
from knowledge_wiki.wiki.frontmatter import parse_frontmatter
from knowledge_wiki.wiki.search import list_wiki_pages, get_all_page_titles, extract_wikilinks

WIKI_ROOT = settings.wiki_root


def _check_broken_links() -> list[str]:
    """查找 [[wikilinks]] 指向不存在页面的死链."""
    broken = []
    wiki_dir = WIKI_ROOT / "wiki"
    all_pages = get_all_page_titles()
    for md in wiki_dir.rglob("*.md"):
        for target in extract_wikilinks(md.read_text()):
            if target not in all_pages:
                broken.append(f"{md.stem} -> [[{target}]] (not found)")
    return broken


def _find_orphan_pages() -> list[str]:
    """查找无入站链接的孤页."""
    wiki_dir = WIKI_ROOT / "wiki"
    all_pages = {md.stem: 0 for md in wiki_dir.rglob("*.md")}
    for md in wiki_dir.rglob("*.md"):
        for target in extract_wikilinks(md.read_text()):
            if target in all_pages:
                all_pages[target] += 1

    exclude = {"Wiki 目录", "操作日志", "知识库概览"}
    return [f"{name} (0 inbound links)" for name, count in all_pages.items()
            if count == 0 and name not in exclude]


def _find_stale_pages(days: int = 30) -> list[str]:
    """查找超过 N 天未更新且标记为 '易过时' 的页面."""
    stale = []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    wiki_dir = WIKI_ROOT / "wiki"
    for md in wiki_dir.rglob("*.md"):
        fm = parse_frontmatter(md)
        if not fm or "易过时" not in fm.get("tags", []):
            continue
        updated_val = fm.get("updated", "")
        if _is_stale(updated_val, cutoff):
            stale.append(f"{md.stem} (updated {updated_val})")
    return stale


def _is_stale(updated_val, cutoff: float) -> bool:
    """检查日期是否早于截止时间."""
    if isinstance(updated_val, str):
        try:
            dt = datetime.strptime(updated_val, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt.timestamp() < cutoff
        except (ValueError, TypeError):
            return False
    elif hasattr(updated_val, 'strftime'):
        dt = datetime.combine(updated_val, datetime.min.time()).replace(tzinfo=timezone.utc)
        return dt.timestamp() < cutoff
    return False


def _find_untagged_pages() -> list[str]:
    """查找无标签的页面."""
    untagged = []
    wiki_dir = WIKI_ROOT / "wiki"
    for md in wiki_dir.rglob("*.md"):
        fm = parse_frontmatter(md)
        if fm and not fm.get("tags"):
            untagged.append(md.stem)
    return untagged


def _unprocessed_raw() -> list[str]:
    """列出 raw/ 中尚未处理的资料."""
    raw_dir = WIKI_ROOT / "raw"
    if not raw_dir.exists():
        return []
    files = []
    for f in sorted(raw_dir.rglob("*")):
        if f.is_file() and f.suffix in (".md", ".txt"):
            files.append(str(f.relative_to(WIKI_ROOT)))
    return files


async def lint_tool() -> str:
    """对 wiki 知识库进行健康检查."""
    pull()

    lines = ["# Wiki 健康检查报告\n"]
    lines.append(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # 死链
    broken = _check_broken_links()
    lines.append(f"## 死链（{len(broken)}）")
    lines.extend(f"- {b}" for b in broken[:20]) if broken else lines.append("未发现死链。")

    # 孤页
    orphans = _find_orphan_pages()
    lines.append(f"\n## 孤页（{len(orphans)}）")
    lines.extend(f"- {o}" for o in orphans[:20]) if orphans else lines.append("未发现孤页。")

    # 过时页面
    stale = _find_stale_pages()
    lines.append(f"\n## 过时页面（{len(stale)}）")
    lines.extend(f"- {s}" for s in stale[:20]) if stale else lines.append("未发现过时页面。")

    # 标签缺失
    untagged = _find_untagged_pages()
    lines.append(f"\n## 标签缺失（{len(untagged)}）")
    lines.extend(f"- {u}" for u in untagged[:20]) if untagged else lines.append("所有页面均已打标签。")

    # 未处理资料
    raw_files = _unprocessed_raw()
    lines.append(f"\n## 未处理资料（{len(raw_files)}）")
    lines.extend(f"- `{r}`" for r in raw_files[:20]) if raw_files else lines.append("raw/ 目录下无未处理资料。")

    # 统计
    pages = list_wiki_pages()
    lines.append(f"\n## 统计")
    lines.append(f"- wiki 页面总数: {len(pages)}")
    lines.append(f"- 资料摘要: {sum(1 for p in pages if p['type'] == 'source')}")
    lines.append(f"- 概念页: {sum(1 for p in pages if p['type'] == 'concept')}")
    lines.append(f"- 综合分析: {sum(1 for p in pages if p['type'] == 'synthesis')}")

    # Phase 4: 语义评估
    try:
        from knowledge_wiki.eval.scorer import get_eval_stats
        from knowledge_wiki.memory.reader import get_stats as mem_stats
        eval_s = get_eval_stats()
        mem_s = mem_stats()
        lines.append(f"\n## 质量评估（Phase 4）")
        if eval_s.get("total", 0) > 0:
            lines.append(f"- 回答评分: {eval_s['stars']} (均分 {eval_s['avg_score']}/5, {eval_s['total']} 次)")
        else:
            lines.append(f"- 回答评分: 暂无（使用 ? 查询后自动评估）")
        if mem_s.get("total", 0) > 0:
            lines.append(f"- 记忆记录: {mem_s['total']} 条")
    except Exception:
        pass

    return "\n".join(lines)
