# ============================================================================
# 中文分词 + 停用词过滤 — 基于 jieba
# ============================================================================
# 两种分词模式：
#   "search" — jieba.cut_for_search，细粒度，用于查询（提高召回）
#   "index"  — jieba.lcut，粗粒度，用于索引（保留语义单元）
#
# 原因：查询时用户输入的"前端代码"需要匹配到"前端代码规范"页面，
# 细粒度切分能覆盖更多子串组合；索引时保留完整语义单元避免噪音。
# ============================================================================

from pathlib import Path
from typing import Literal


def _get_dict_dir() -> Path:
    """获取词典目录。"""
    return Path(__file__).resolve().parent / "dict"


def load_custom_dict(dict_path: Path | None = None) -> None:
    """加载自定义词典，扩充技术专有名词。

    调用时机：
    - 服务启动时
    - lint 扫描新概念后动态补充

    Args:
        dict_path: 自定义词典路径，默认 dict/custom.txt
    """
    import jieba

    if dict_path is None:
        dict_path = _get_dict_dir() / "custom.txt"
    if dict_path.exists():
        jieba.load_userdict(str(dict_path))


def _load_stopwords(path: Path | None = None) -> set[str]:
    """加载停用词表（内部，惰性加载）。"""
    if path is None:
        path = _get_dict_dir() / "stopwords.txt"
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")}


# 模块级别停用词缓存（惰性加载）
_stopwords: set[str] | None = None


def _get_stopwords() -> set[str]:
    """获取停用词集合（惰性初始化）。"""
    global _stopwords
    if _stopwords is None:
        _stopwords = _load_stopwords()
    return _stopwords


def tokenize(text: str, mode: Literal["search", "index"] = "search") -> list[str]:
    """中文分词。

    Args:
        text: 待分词文本
        mode: "search" 细粒度（查询用） / "index" 粗粒度（索引用）

    Returns:
        分词后的词语列表

    Examples:
        tokenize("前端代码规范", mode="index")   → ["前端", "代码", "规范", "前端代码规范"]
        tokenize("前端代码", mode="search")      → ["前端", "代码", "前端代码"]
    """
    import jieba

    if mode == "search":
        tokens = list(jieba.cut_for_search(text))
    else:
        tokens = list(jieba.lcut(text))

    # 过滤空格和纯标点
    tokens = [t.strip() for t in tokens if t.strip()]
    return [t for t in tokens if t not in {" ", "\t", "\n", ".", ",", "。", "，", "、"}]


def remove_stopwords(tokens: list[str]) -> list[str]:
    """去掉停用词。

    Args:
        tokens: 分词后的词语列表

    Returns:
        去掉停用词后的列表
    """
    stopwords = _get_stopwords()
    return [t for t in tokens if t.lower() not in stopwords]
