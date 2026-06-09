# ============================================================================
# 语义检索引擎 — Ollama Embedding 向量生成 + 余弦相似度搜索
# ============================================================================
# 使用 Ollama 的 embedding API 将 wiki 页面和查询转为向量，
# 通过余弦相似度补充 BM25 无法捕获的语义近义词匹配。
#
# 向量存储：pickle 文件（< 1000 页无需 FAISS），递增增量更新。
# 模型：nomic-embed-text（Ollama 默认 embedding 模型，多语言支持）
# ============================================================================

import json
import logging
import math
import pickle
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from knowledge_wiki.config import settings
from knowledge_wiki.wiki.retrieval.config import retrieval_config

_log = logging.getLogger(__name__)

# Ollama embedding API endpoint
OLLAMA_EMBED_URL = f"{settings.ollama_base_url}/api/embeddings"

# 默认 embedding 模型（可通过 settings 覆盖）
EMBED_MODEL = getattr(settings, "ollama_model_embed", "nomic-embed-text:latest")

# 索引缓存路径
EMBED_CACHE_DIR = settings.wiki_root / ".cache" / "retrieval"
EMBED_INDEX_PATH = EMBED_CACHE_DIR / "embedding.pkl"

# 分块大小（每页最多 N 字符，避免超长页面）
MAX_CHARS_PER_PAGE = 8000


@dataclass
class EmbeddingIndex:
    """向量索引实体（可序列化）."""

    version: int = 1
    built_at: str = ""  # ISO 时间戳
    model: str = ""  # 使用的 embedding 模型
    num_docs: int = 0
    # 文档路径 → 向量（numpy array 不可序列化，存为 list）
    vectors: dict[str, list[float]] = field(default_factory=dict)
    # 文档路径 → 标题（用于结果展示）
    titles: dict[str, str] = field(default_factory=dict)
    # 文档路径 → SHA256（用于增量更新）
    hashes: dict[str, str] = field(default_factory=dict)


def _get_page_text(path: Path) -> str:
    """从 wiki 页面提取用于 embedding 的文本（frontmatter 摘要 + 正文前 N 字）.

    优先使用 frontmatter 中的 title/tags/summary，再拼接正文。
    这样 embedding 能捕获页面主题而非全文噪声。
    """
    from knowledge_wiki.wiki.frontmatter import parse_frontmatter

    text = ""
    fm = parse_frontmatter(path)
    if fm:
        title = fm.get("title", "")
        tags = fm.get("tags", [])
        text = f"{title}. {' '.join(tags) if tags else ''}"
    # 正文（去 frontmatter）
    raw = path.read_text(encoding="utf-8")
    body = raw.split("---\n", 2)[-1] if raw.startswith("---") else raw
    text += "\n" + body[:MAX_CHARS_PER_PAGE]
    return text.strip()


def _call_ollama_embed(text: str, retries: int = 2) -> list[float] | None:
    """调用 Ollama embedding API 生成向量（带指数退避重试）.

    Args:
        text: 待嵌入文本
        retries: 最大重试次数

    Returns:
        向量（浮点数列表）或 None
    """
    for attempt in range(retries + 1):
        try:
            body = json.dumps({
                "model": EMBED_MODEL,
                "prompt": text[:6000],  # Ollama embedding 输入限制
            }).encode()

            req = urllib.request.Request(
                OLLAMA_EMBED_URL,
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                embedding = result.get("embedding", [])
                if embedding:
                    return embedding
                _log.warning("Ollama embed 返回空向量")

        except Exception as e:
            if attempt < retries:
                delay = 1.5 ** attempt
                _log.warning("Ollama embed 失败 (attempt %d/%d): %s — retrying in %.1fs",
                             attempt + 1, retries + 1, e, delay)
                time.sleep(delay)
            else:
                _log.error("Ollama embed 失败 after %d attempts: %s", retries + 1, e)

    return None


# ============================================================================
# 余弦相似度（纯 Python，无需 numpy）
# ============================================================================

def _dot(a: list[float], b: list[float]) -> float:
    """向量点积."""
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    """向量 L2 范数."""
    return math.sqrt(sum(x * x for x in a))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度（纯 Python 实现）.

    Args:
        a, b: 等长向量

    Returns:
        余弦相似度 [0, 1]
    """
    if len(a) != len(b):
        return 0.0
    norm_a, norm_b = _norm(a), _norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return _dot(a, b) / (norm_a * norm_b)


# ============================================================================
# 索引构建与搜索
# ============================================================================

def build_embedding_index(
    wiki_dir: Path | None = None,
    force: bool = False,
) -> EmbeddingIndex | None:
    """扫描 wiki/ 下所有 .md 文件，生成向量索引.

    Args:
        wiki_dir: wiki 目录路径
        force: 强制全量重建（忽略增量）

    Returns:
        EmbeddingIndex 或 None（Ollama 不可用时）
    """
    from datetime import datetime, timezone
    from hashlib import sha256

    if wiki_dir is None:
        wiki_dir = settings.wiki_root / "wiki"

    # 尝试增量更新
    existing = load_embedding_index()
    if existing is not None and not force and existing.model == EMBED_MODEL:
        index = existing
        _log.info("加载已有 embedding 索引，%d 页，检查增量...", index.num_docs)
    else:
        index = EmbeddingIndex(
            version=2,
            built_at=datetime.now(timezone.utc).isoformat(),
            model=EMBED_MODEL,
        )

    # 扫描所有 .md 文件
    exclude_stems = {"wiki 目录", "wiki目录", "操作日志"}
    md_files = sorted(
        f for f in wiki_dir.rglob("*.md")
        if f.stem.lower() not in exclude_stems and not f.name.startswith("hot")
    )

    new_count = 0
    for md_path in md_files:
        rel_path = str(md_path.relative_to(settings.wiki_root))
        content_hash = sha256(md_path.read_bytes()).hexdigest()

        # 增量跳过未变更的
        if rel_path in index.hashes and index.hashes[rel_path] == content_hash:
            continue

        # 生成向量
        text = _get_page_text(md_path)
        vec = _call_ollama_embed(text)
        if vec is None:
            _log.warning("跳过 %s（embedding 生成失败）", rel_path)
            continue

        # 更新索引
        index.vectors[rel_path] = vec
        index.titles[rel_path] = md_path.stem
        index.hashes[rel_path] = content_hash
        new_count += 1

    # 清理已删除的文件
    valid_paths = {str(f.relative_to(settings.wiki_root)) for f in md_files}
    for path_key in list(index.vectors.keys()):
        if path_key not in valid_paths:
            del index.vectors[path_key]
            del index.titles[path_key]
            del index.hashes[path_key]

    index.num_docs = len(index.vectors)
    index.built_at = datetime.now(timezone.utc).isoformat()

    if new_count > 0:
        save_embedding_index(index)
        _log.info("Embedding 索引更新完成：+%d 新增，总计 %d 页", new_count, index.num_docs)

    return index


def save_embedding_index(index: EmbeddingIndex, path: Path | None = None) -> None:
    """序列化向量索引到 pickle（原子写入）.

    Args:
        index: EmbeddingIndex 实例
        path: 存储路径
    """
    if path is None:
        path = EMBED_INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(".pkl.tmp")
    with open(tmp, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


def load_embedding_index(path: Path | None = None) -> EmbeddingIndex | None:
    """从磁盘加载 embedding 索引.

    Args:
        path: 索引缓存路径

    Returns:
        EmbeddingIndex 或 None（文件不存在/损坏/版本不匹配）
    """
    if path is None:
        path = EMBED_INDEX_PATH

    if not path.exists():
        return None

    try:
        with open(path, "rb") as f:
            index = pickle.load(f)
        if not isinstance(index, EmbeddingIndex):
            return None
        if index.version < 2:
            return None  # 旧版本，强制重建
        return index
    except Exception:
        return None


def semantic_search(
    query: str,
    index: EmbeddingIndex,
    top_k: int = 20,
) -> list[tuple[str, str, float]]:
    """语义搜索：查询向量 → 余弦相似度排序 → Top-K.

    Args:
        query: 查询文本
        index: embedding 索引
        top_k: 返回结果数

    Returns:
        [(路径, 标题, 相似度分数), ...] 按相似度降序
    """
    if not index.vectors:
        return []

    q_vec = _call_ollama_embed(query)
    if q_vec is None:
        return []

    # 计算所有文档的余弦相似度
    scores = []
    for path, doc_vec in index.vectors.items():
        sim = cosine_similarity(q_vec, doc_vec)
        if sim > 0:
            title = index.titles.get(path, Path(path).stem)
            scores.append((path, title, sim))

    # 降序排序，取 top_k
    scores.sort(key=lambda x: -x[2])
    return scores[:top_k]


def embedding_index_ready() -> bool:
    """检查 embedding 索引是否可用."""
    idx = load_embedding_index()
    if idx is None or idx.num_docs == 0:
        return False
    return True
