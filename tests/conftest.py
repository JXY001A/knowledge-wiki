"""共享测试 fixtures."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# 将 src/ 加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_wiki_root():
    """临时 wiki 根目录."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # 创建基本目录结构
        (root / "wiki").mkdir()
        (root / "raw" / "收件箱").mkdir(parents=True)
        (root / "wiki" / "操作日志.md").write_text(
            "# 操作日志\n\n> 每次 ingest / query / lint\n"
        )
        yield root


@pytest.fixture
def sample_frontmatter_md():
    """包含 frontmatter 的示例 markdown."""
    return """---
title: 测试页面
type: concept
tags: [概念, 测试]
created: 2026-05-23
updated: 2026-05-23
confidence: high
---

> 这是一个测试页面。

## 是什么

测试概念的定义。

## 相关

- [[Wiki 目录]]
"""


@pytest.fixture
def sample_page_file(temp_wiki_root, sample_frontmatter_md):
    """创建示例 wiki 页面文件."""
    dest = temp_wiki_root / "wiki" / "概念"
    dest.mkdir(parents=True, exist_ok=True)
    filepath = dest / "测试概念.md"
    filepath.write_text(sample_frontmatter_md)
    return filepath
