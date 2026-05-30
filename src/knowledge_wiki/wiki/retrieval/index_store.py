# ============================================================================
# 索引序列化与版本管理 — pickle + zstd 压缩
# ============================================================================
# 索引存储在 .cache/retrieval/ 下（不入 git），启动时自动加载或重建。
# 校验链：版本号 → 文档数 → 抽样 hash → 任一失败则全量重建。
# ============================================================================

from pathlib import Path
from typing import TYPE_CHECKING

from knowledge_wiki.config import settings

if TYPE_CHECKING:
    from knowledge_wiki.wiki.retrieval.bm25 import BM25Index


def _cache_path() -> Path:
    """获取索引缓存文件路径。"""
    return settings.wiki_root / ".cache" / "retrieval" / "bm25.pkl.zst"


def save_index(index: "BM25Index", path: Path | None = None) -> None:
    """序列化索引到磁盘（zstd 压缩 pickle，原子写入）。

    先写 .tmp 文件，成功后原子替换，避免并发损坏。

    Args:
        index: BM25Index 实例
        path: 存储路径，默认 .cache/retrieval/bm25.pkl.zst
    """
    import pickle
    import zstandard as zstd

    if path is None:
        path = _cache_path()

    path.parent.mkdir(parents=True, exist_ok=True)

    # 序列化
    data = pickle.dumps(index, protocol=pickle.HIGHEST_PROTOCOL)

    # zstd 压缩（level=3：速度与体积的平衡点）
    cctx = zstd.ZstdCompressor(level=3)
    compressed = cctx.compress(data)

    # 原子写入：先 .tmp，再替换
    tmp_path = path.with_suffix(".pkl.zst.tmp")
    tmp_path.write_bytes(compressed)
    tmp_path.replace(path)


def load_index(path: Path | None = None) -> "BM25Index | None":
    """从磁盘加载索引。校验失败返回 None。

    Args:
        path: 索引缓存路径

    Returns:
        BM25Index 或 None（需重建）
    """
    import pickle
    import zstandard as zstd

    from knowledge_wiki.wiki.retrieval.config import retrieval_config

    if path is None:
        path = _cache_path()

    if not path.exists():
        return None

    try:
        compressed = path.read_bytes()
        dctx = zstd.ZstdDecompressor()
        data = dctx.decompress(compressed)
        index = pickle.loads(data)

        # 校验版本号
        if index.version != retrieval_config.index_version:
            return None

        return index
    except Exception:
        return None


def index_is_fresh(index: "BM25Index", wiki_dir: Path | None = None) -> bool:
    """检查索引是否与当前 wiki/ 保持一致。

    校验：
      1. 文档数量匹配
      2. 抽样 3 个页面 hash 一致

    Args:
        index: 已加载的索引
        wiki_dir: wiki 目录路径

    Returns:
        True 表示索引可用，False 表示需要重建
    """
    from hashlib import sha256

    if wiki_dir is None:
        wiki_dir = settings.wiki_root / "wiki"

    # 当前实际 .md 文件数（排除特殊页）
    exclude_stems = {"wiki 目录", "wiki目录", "操作日志"}
    actual_files = [
        f for f in wiki_dir.rglob("*.md")
        if f.stem.lower() not in exclude_stems and not f.name.startswith("hot")
    ]

    if len(actual_files) != index.num_docs:
        return False

    # 抽样 3 个页面做 hash 校验
    sample = list(actual_files)[:3]
    for md_path in sample:
        current_hash = sha256(md_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        # 在 index 中查找该文件
        rel_path = str(md_path.relative_to(settings.wiki_root))
        found = any(
            meta.sha256 == current_hash
            for meta in index.doc_meta.values()
            if meta.path == rel_path
        )
        if not found:
            return False

    return True
