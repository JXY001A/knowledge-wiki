"""YAML frontmatter 解析 / 剥离."""

from pathlib import Path
import yaml


def parse_frontmatter(filepath: Path) -> dict | None:
    """解析 wiki 页面的 YAML frontmatter."""
    if not filepath.exists():
        return None
    text = filepath.read_text()
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    try:
        return yaml.safe_load(text[3:end])
    except Exception:
        return {}


def strip_frontmatter(text: str) -> str:
    """剥离 YAML frontmatter，返回正文——防止 LLM 将元数据当内容处理."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].strip()
    return text


def extract_frontmatter_field(filepath: Path, field: str) -> str | None:
    """从 frontmatter 中提取指定字段."""
    fm = parse_frontmatter(filepath)
    if fm:
        return fm.get(field)
    return None
