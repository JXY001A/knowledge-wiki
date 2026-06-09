# ============================================================================
# 知识深度加工 — 语义关联发现 + LLM 矛盾检测
# ============================================================================
# 1. 语义关联发现：计算所有 wiki 页面间的余弦相似度，
#    发现高相似度但无 wikilink 的页面对，建议关联。
# 2. 矛盾检测：用 LLM 对比两篇页面内容，检测冲突声明。
# ============================================================================

import json
import logging
import re
import urllib.request
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from knowledge_wiki.config import settings

_log = logging.getLogger(__name__)


@dataclass
class RelationSuggestion:
    """关联建议."""
    page1: str  # 页面标题
    page2: str
    similarity: float  # 余弦相似度 [0, 1]
    has_wikilink: bool = False  # 是否已有交叉引用
    suggested_action: str = ""  # "add_wikilink" | "merge" | "review"


@dataclass
class Contradiction:
    """检测到的矛盾."""
    page1: str
    page2: str
    claim1: str  # 页面1中的声明
    claim2: str  # 页面2中的声明
    resolution: str = ""  # LLM 建议的解决方式
    severity: str = "low"  # low | medium | high


# ============================================================================
# 1. 语义关联发现
# ============================================================================

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]")


def discover_relations(
    wiki_dir: Path | None = None,
    min_similarity: float = 0.7,
    max_suggestions: int = 20,
) -> list[RelationSuggestion]:
    """发现高相似度但无 wikilink 的页面对，建议建立关联.

    基于 embedding 索引中的向量高效计算相似度，
    不需要为每对页面重新加载文件。

    Args:
        wiki_dir: wiki 目录路径
        min_similarity: 最小相似度阈值
        max_suggestions: 最多返回 N 条建议

    Returns:
        按相似度降序的关联建议列表
    """
    from knowledge_wiki.wiki.retrieval.embedding import (
        load_embedding_index,
        cosine_similarity,
    )

    if wiki_dir is None:
        wiki_dir = settings.wiki_root / "wiki"

    # 加载 embedding 索引
    idx = load_embedding_index()
    if idx is None or idx.num_docs < 2:
        _log.info("Embedding 索引不可用，无法发现关联")
        return []

    vectors = idx.vectors
    titles = idx.titles

    # 提取所有页面的 wikilink 关系
    wikilink_graph: dict[str, set[str]] = {}
    for rel_path in vectors:
        page_path = settings.wiki_root / rel_path
        page_title = titles.get(rel_path, Path(rel_path).stem)
        if page_path.exists():
            try:
                text = page_path.read_text(encoding="utf-8")
                links = set(WIKILINK_RE.findall(text))
                wikilink_graph[rel_path] = links
            except Exception:
                wikilink_graph[rel_path] = set()
        else:
            wikilink_graph[rel_path] = set()

    # 计算所有页面对的相似度（限制组合数，避免 O(n²) 爆炸）
    paths = sorted(vectors.keys())
    if len(paths) > 200:
        # 页面太多时采样：只比较前 200 个
        paths = paths[:200]
        _log.warning("页面数 > 200，采样前 200 个计算关系")

    suggestions = []
    for p1, p2 in combinations(paths, 2):
        v1, v2 = vectors[p1], vectors[p2]
        sim = cosine_similarity(v1, v2)

        if sim < min_similarity:
            continue

        title1 = titles.get(p1, Path(p1).stem)
        title2 = titles.get(p2, Path(p2).stem)

        # 检查是否已有 wikilink
        has_link = (
            title2 in wikilink_graph.get(p1, set())
            or title1 in wikilink_graph.get(p2, set())
        )

        if has_link:
            continue  # 已有交叉引用，跳过

        # 建议操作
        if sim > 0.9:
            action = "merge"  # 极高相似度，建议合并
        else:
            action = "add_wikilink"  # 高相似度，建议添加交叉引用

        suggestions.append(RelationSuggestion(
            page1=title1,
            page2=title2,
            similarity=round(sim, 3),
            has_wikilink=False,
            suggested_action=action,
        ))

    # 按相似度降序
    suggestions.sort(key=lambda s: -s.similarity)
    return suggestions[:max_suggestions]


def discover_relations_markdown() -> str:
    """生成关联建议的 markdown 文本.

    Returns:
        markdown 格式的建议列表
    """
    suggestions = discover_relations()

    if not suggestions:
        return "✅ 未发现缺少关联的高相似度页面对。"

    lines = [
        "## 🔗 语义关联建议",
        "",
        f"发现 {len(suggestions)} 对高相似度但无交叉引用的页面：",
        "",
    ]

    for s in suggestions:
        action_icon = "🔄" if s.suggested_action == "merge" else "🔗"
        action_text = "建议合并" if s.suggested_action == "merge" else "建议添加交叉引用"
        lines.append(
            f"- **{action_icon} [[{s.page1}]] ↔ [[{s.page2}]]** "
            f"（相似度 {s.similarity:.0%}）— {action_text}"
        )

    lines.append("")
    lines.append("可在 Obsidian 中手动添加 `[[wikilink]]` 或合并页面。")

    return "\n".join(lines)


# ============================================================================
# 2. LLM 矛盾检测
# ============================================================================

CONTRADICTION_PROMPT = """你是知识库质量审查员。对比以下两篇 wiki 页面的内容，检测是否存在矛盾或冲突声明。

输出 JSON（严格按此格式）：
{
  "has_contradiction": true/false,
  "claim1": "页面1中的声明（原文摘录，≤100字）",
  "claim2": "页面2中的声明（原文摘录，≤100字）",
  "resolution": "解决建议（≤100字）",
  "severity": "high/medium/low"
}

规则：
- has_contradiction: 仅在明确发现矛盾时为 true
- severity: high=核心事实冲突, medium=观点/侧重不同, low=细节差异
- 没有矛盾时 claim1/claim2 填空字符串
- 只输出 JSON，不要 markdown 代码块"""


def find_contradictions(
    page1_path: str,
    page2_path: str,
    model: str = "",
) -> Contradiction | None:
    """用 DeepSeek 对比两个 wiki 页面，检测矛盾声明.

    Args:
        page1_path: 页面1的 wiki 相对路径
        page2_path: 页面2的 wiki 相对路径
        model: 使用的模型（默认 deepseek-chat）

    Returns:
        Contradiction 或 None（无矛盾或检测失败）
    """
    api_key = settings.deepseek_api_key
    if not api_key:
        _log.warning("DEEPSEEK_API_KEY not set, skip contradiction check")
        return None

    if not model:
        model = settings.deepseek_model_eval

    # 读取两篇页面
    p1 = settings.wiki_root / page1_path
    p2 = settings.wiki_root / page2_path

    if not p1.exists() or not p2.exists():
        return None

    text1 = p1.read_text(encoding="utf-8")[:4000]
    text2 = p2.read_text(encoding="utf-8")[:4000]

    from knowledge_wiki.wiki.frontmatter import parse_frontmatter
    fm1 = parse_frontmatter(p1)
    fm2 = parse_frontmatter(p2)
    title1 = fm1.get("title", p1.stem) if fm1 else p1.stem
    title2 = fm2.get("title", p2.stem) if fm2 else p2.stem

    user_content = (
        f"## 页面1：{title1}\n\n{text1}\n\n"
        f"## 页面2：{title2}\n\n{text2}"
    )

    try:
        body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": CONTRADICTION_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 500,
        }).encode()

        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = json.loads(resp.read())
            content = raw["choices"][0]["message"]["content"]

        from knowledge_wiki.llm.base import extract_json
        json_str = extract_json(content)
        if not json_str:
            return None

        data = json.loads(json_str)
        if not data.get("has_contradiction"):
            return None

        return Contradiction(
            page1=title1,
            page2=title2,
            claim1=data.get("claim1", ""),
            claim2=data.get("claim2", ""),
            resolution=data.get("resolution", ""),
            severity=data.get("severity", "low"),
        )

    except Exception as e:
        _log.warning("矛盾检测失败: %s", e)
        return None


def run_contradiction_scan(max_pairs: int = 10) -> list[Contradiction]:
    """扫描高相似度页面对，检测矛盾.

    先通过语义相似度找到候选对，再逐个用 LLM 检测矛盾。

    Args:
        max_pairs: 最多检测 N 对页面

    Returns:
        检测到的矛盾列表
    """
    # 先获取高相似度页面对
    suggestions = discover_relations(min_similarity=0.5, max_suggestions=max_pairs)
    if not suggestions:
        return []

    contradictions = []
    for s in suggestions:
        # 找到两个页面的路径
        from knowledge_wiki.wiki.retrieval.layered import _find_page_by_title
        wiki_dir = settings.wiki_root / "wiki"
        p1_file = _find_page_by_title(s.page1, wiki_dir)
        p2_file = _find_page_by_title(s.page2, wiki_dir)
        if not p1_file or not p2_file:
            continue

        rel1 = str(p1_file.relative_to(settings.wiki_root))
        rel2 = str(p2_file.relative_to(settings.wiki_root))
        result = find_contradictions(rel1, rel2)
        if result:
            contradictions.append(result)

    return contradictions
