"""知识缺口检测 — 从低分评估中识别知识盲区，生成待摄取清单.

分析来源：
    1. memory_events 中 score ≤ 2 的 eval/query 记录
    2. concept_coverage 中缺失的概念
    3. raw/ 中未处理的资料
"""

import json
import re
from collections import Counter
from knowledge_wiki.memory.db import get_db, init_schema


def detect_gaps(min_score: int = 3) -> list[dict]:
    """从低分评估记录中提取知识缺口.

    Args:
        min_score: 评分 ≤ 此值的记录视为有缺口

    Returns:
        缺口列表 [{"question": "...", "score": N, "gaps": ["..."], "improvement": "..."}]
    """
    conn = get_db()
    init_schema(conn)

    rows = conn.execute(
        "SELECT * FROM memory_events WHERE score IS NOT NULL AND score <= ? "
        "ORDER BY created_at DESC LIMIT 30",
        [min_score],
    ).fetchall()
    conn.close()

    gaps = []
    for r in rows:
        details = r["details"] or ""
        summary = r["summary"] or ""

        # 从 details 中提取缺口列表
        gap_items = _extract_gaps_from_text(details)

        gaps.append({
            "question": summary[:100],
            "score": r["score"],
            "gaps": gap_items,
            "created_at": r["created_at"][:10] if r["created_at"] else "",
        })

    return gaps


def _extract_gaps_from_text(text: str) -> list[str]:
    """从评估文本中提取缺口项.

    支持两种格式：
        1. JSON: {"gaps": ["缺 X", "缺 Y"]}
        2. 自然语言: 知识缺口：缺X、缺Y
    """
    # 尝试 JSON 解析
    try:
        m = re.search(r"\{[^{}]*\"gaps\"[^{}]*\}", text, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            return data.get("gaps", [])
    except (json.JSONDecodeError, KeyError):
        pass

    # 自然语言提取
    gaps = []
    for pattern in [r"知识缺口[：:]\s*(.+?)(?:\n|$)", r"缺失[：:]\s*(.+?)(?:\n|$)"]:
        m = re.search(pattern, text)
        if m:
            items = re.split(r"[、,，;；]", m.group(1))
            gaps.extend(i.strip() for i in items if len(i.strip()) > 2)

    return gaps[:5]


def generate_ingest_list() -> dict:
    """生成待摄取清单：缺口概念 + 未处理 raw 资料.

    Returns:
        {"gaps": [...], "unprocessed_raw": [...], "missing_concepts": [...]}
    """
    from knowledge_wiki.wiki.search import get_all_page_titles
    from knowledge_wiki.memory.semantic import concept_coverage

    result = {"gaps": [], "unprocessed_raw": [], "missing_concepts": []}

    # 1. 知识缺口
    gaps = detect_gaps()
    all_gaps = []
    for g in gaps:
        all_gaps.extend(g["gaps"])

    # 统计最高频缺口
    gap_counts = Counter(all_gaps)
    result["gaps"] = [{"topic": k, "count": v} for k, v in gap_counts.most_common(10)]

    # 2. 未处理 raw 资料
    from knowledge_wiki.config import settings
    raw_dir = settings.wiki_root / "raw"
    if raw_dir.exists():
        unprocessed = []
        for f in sorted(raw_dir.rglob("*")):
            if f.is_file() and f.suffix in (".md", ".txt") and "assets" not in str(f):
                unprocessed.append(str(f.relative_to(settings.wiki_root)))
        result["unprocessed_raw"] = unprocessed[:10]

    # 3. 缺失概念
    coverage = concept_coverage()
    result["missing_concepts"] = coverage.get("missing_concepts", [])[:10]

    return result
