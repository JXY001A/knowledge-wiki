# ============================================================================
# 分层组装 — Layer 1/2/3 结构化上下文生成
# ============================================================================
# 把 BM25 Top-N 结果组装为三层结构化 markdown，让 LLM 先看结论再看证据：
#   Layer 1（编译真相）: Top-1 frontmatter + 正文前 400 字
#   Layer 2（交叉引用）: Top-1 的 wikilink 邻居标题 + 一句话摘要
#   Layer 3（证据补充）: Top-2..N 全文 + 操作日志匹配条目
#
# Token 预算：总量 8000，L1=1500, L2=1000, L3=5500（可配置）
# ============================================================================

import re
import textwrap
from pathlib import Path

from knowledge_wiki.config import settings
from knowledge_wiki.wiki.retrieval.bm25 import BM25Result
from knowledge_wiki.wiki.retrieval.config import retrieval_config

# 提取 wikilink 的正则（匹配 [[target]] 与 [[target|alias]]）
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]")


def _extract_first_sentence(text: str) -> str:
    """从正文中提取第一句话作为摘要。

    Args:
        text: 页面正文

    Returns:
        第一句话（中英文句号、问号、感叹号截断）
    """
    # 去掉 frontmatter（如果正文仍包含）
    if text.startswith("---"):
        parts = text.split("---\n", 2)
        text = parts[-1] if len(parts) >= 3 else text

    # 去掉标题行（以 # 开头）
    lines = text.strip().splitlines()
    body_lines = [l for l in lines if not l.startswith("#") and l.strip()]
    body = " ".join(body_lines)

    # 按第一个句号/问号/感叹号截断
    for delim in ["。", "？", "！", ".", "?", "!"]:
        idx = body.find(delim)
        if idx > 10:  # 至少 10 个字符，避免截到版本号等
            return body[:idx + 1].strip()

    # 没有句号则取前 100 字
    return body[:100].strip()


def _estimate_tokens(text: str) -> int:
    """粗估 token 数。中英文混合：1 token ≈ 2 字符。

    Args:
        text: 待估算文本

    Returns:
        估算 token 数
    """
    return len(text) // 2


def assemble_layered(
    query: str,
    top_n: list[BM25Result],
    wiki_dir: Path | None = None,
) -> str:
    """组装三层结构化 markdown 上下文。

    Args:
        query: 原始查询
        top_n: 经 BM25 排序后的结果列表（已截断到 final_top_n）
        wiki_dir: wiki 目录路径

    Returns:
        分层结构化的 markdown 文本
    """
    if wiki_dir is None:
        wiki_dir = settings.wiki_root / "wiki"

    cfg = retrieval_config

    if not top_n:
        return f"未在 wiki 中找到与「{query}」相关的页面。"

    # ---- Layer 1: 编译真相 ----
    layer1 = _build_layer1(query, top_n[0], wiki_dir, cfg)

    # ---- Layer 2: 交叉引用 ----
    layer2 = _build_layer2(top_n[0], wiki_dir, cfg)

    # ---- Layer 3: 证据补充 ----
    layer3 = _build_layer3(query, top_n[1:], wiki_dir, cfg)

    # 组装最终 markdown
    parts = [
        f"# 检索结果：{query}\n",
        "## 编译真相\n",
        layer1,
        "---\n",
        "## 交叉引用\n",
        layer2,
        "---\n",
        "## 证据补充\n",
        layer3,
        "---\n",
        "_本结果由 retrieval pipeline v1 生成 | catalog→bm25→layered_",
    ]
    return "\n".join(parts)


def _build_layer1(
    query: str,
    top1: BM25Result,
    wiki_dir: Path,
    cfg,
) -> str:
    """构建 Layer 1：Top-1 文档的 frontmatter + 正文前 N 字。

    Args:
        top1: BM25 排名第一的结果
        wiki_dir: wiki 目录
        cfg: 检索配置

    Returns:
        Layer 1 的 markdown 文本
    """
    filepath = wiki_dir / top1.path
    if not filepath.exists():
        return f"**[[{top1.title}]]** | 文件未找到\n"

    content = filepath.read_text(encoding="utf-8")

    # 解析 frontmatter
    from knowledge_wiki.wiki.frontmatter import parse_frontmatter

    fm = parse_frontmatter(filepath)

    lines: list[str] = []

    if fm:
        lines.append(f"**[[{fm.get('title', top1.title)}]]**")
        lines.append(f"| type: {fm.get('type', 'unknown')}")
        lines.append(f"| confidence: {fm.get('confidence', '')}")
        tags = fm.get("tags", [])
        if tags:
            lines.append(f"| tags: {', '.join(tags) if isinstance(tags, list) else tags}")
        lines.append("")
        # 正文 = frontmatter 之后的内容
        body = content.split("---\n", 2)[-1] if content.startswith("---") else content
    else:
        lines.append(f"**[[{top1.title}]]**")
        lines.append("")
        body = content

    # 正文前 N 字
    body_preview = body[:cfg.layer_1_body_chars].strip()
    lines.append(body_preview)

    layer1_text = "\n".join(lines)

    # 截断到 Layer 1 预算
    while _estimate_tokens(layer1_text) > cfg.layer_1_budget and cfg.layer_1_body_chars > 100:
        cfg.layer_1_body_chars -= 100
        body_preview = body[:cfg.layer_1_body_chars].strip()
        lines[-1] = body_preview
        layer1_text = "\n".join(lines)

    return layer1_text


def _build_layer2(
    top1: BM25Result,
    wiki_dir: Path,
    cfg,
) -> str:
    """构建 Layer 2：Top-1 的 wikilink 邻居摘要。

    Args:
        top1: BM25 排名第一的结果
        wiki_dir: wiki 目录
        cfg: 检索配置

    Returns:
        Layer 2 的 markdown 文本
    """
    filepath = wiki_dir / top1.path
    if not filepath.exists():
        return "_无交叉引用_\n"

    content = filepath.read_text(encoding="utf-8")

    # 提取所有 wikilink 目标
    links = WIKILINK_RE.findall(content)
    # 去重，排除自引用
    unique_links = list(dict.fromkeys(links))  # 保序去重
    neighbors = [l for l in unique_links if l != top1.title]

    if not neighbors:
        return "_无交叉引用_\n"

    lines: list[str] = []
    budget_remaining = cfg.layer_2_budget

    for nb in neighbors:
        if budget_remaining <= 0:
            break

        # 查找邻居文件（搜索 wiki 目录）
        nb_file = _find_page_by_title(nb, wiki_dir)
        if nb_file:
            nb_text = nb_file.read_text(encoding="utf-8")
            summary = _extract_first_sentence(nb_text)
        else:
            summary = nb

        line = f"- **[[{nb}]]** — {summary}\n"
        lines.append(line)
        budget_remaining -= _estimate_tokens(line)

    return "".join(lines) if lines else "_无交叉引用_\n"


def _build_layer3(
    query: str,
    rest: list[BM25Result],
    wiki_dir: Path,
    cfg,
) -> str:
    """构建 Layer 3：Top-2..N 全文 + 操作日志匹配条目。

    Args:
        rest: Top-2 之后的 BM25 结果
        wiki_dir: wiki 目录
        cfg: 检索配置

    Returns:
        Layer 3 的 markdown 文本
    """
    if not rest:
        return "_无更多证据_\n"

    # 计算每个文档的 token 预算（平均分配）
    budget_per_doc = max(500, cfg.layer_3_budget // len(rest))
    lines: list[str] = []

    for r in rest:
        filepath = settings.wiki_root / r.path
        if not filepath.exists():
            continue

        content = filepath.read_text(encoding="utf-8")

        lines.append(f"### [[{r.title}]] | score={r.score:.2f}\n")

        # 按预算截断
        if _estimate_tokens(content) > budget_per_doc:
            content = content[:budget_per_doc * 2]  # 2 字符 ≈ 1 token
            content += "\n\n...（已截断）\n"

        lines.append(content)
        lines.append("")

    return "".join(lines)


def _find_page_by_title(title: str, wiki_dir: Path) -> Path | None:
    """在 wiki/ 下按标题查找页面文件。

    优先精确匹配文件名，回退到搜索 frontmatter。

    Args:
        title: 页面标题
        wiki_dir: wiki 目录

    Returns:
        文件路径或 None
    """
    # 精确匹配文件名（title 即文件名）
    exact = wiki_dir / f"{title}.md"
    if exact.exists():
        return exact

    # 递归搜索
    for md in wiki_dir.rglob("*.md"):
        if md.stem == title:
            return md

    # 搜索 frontmatter 中的 title
    from knowledge_wiki.wiki.frontmatter import parse_frontmatter

    for md in wiki_dir.rglob("*.md"):
        fm = parse_frontmatter(md)
        if fm and fm.get("title") == title:
            return md

    return None
