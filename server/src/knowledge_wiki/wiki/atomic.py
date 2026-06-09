"""原子文件操作 — 防止写入中断导致文件损坏.

原则：先写 .tmp 临时文件，成功后再 os.replace() 原子替换目标。
os.replace 在 POSIX 系统上是原子操作，不会出现"写一半"的情况。

使用方式：
    from knowledge_wiki.wiki.atomic import atomic_write, atomic_update

    # 新建/覆盖文件
    atomic_write(filepath, content)

    # 读取 → 变换 → 原子写回（更新已有文件）
    atomic_update(filepath, lambda old: old + new_entry)
"""

import os
from pathlib import Path
from typing import Callable


def atomic_write(filepath: Path, content: str) -> None:
    """原子写入文件：先写 .tmp，成功后再 replace 到目标路径.

    Args:
        filepath: 目标文件路径
        content: 要写入的内容
    """
    # 确保父目录存在
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # 写入临时文件
    tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")

    # 原子替换（POSIX 保证此操作不会被中断）
    os.replace(str(tmp_path), str(filepath))


def atomic_update(filepath: Path, transform: Callable[[str], str]) -> None:
    """原子更新已有文件：读取 → 变换 → 原子写回.

    Args:
        filepath: 目标文件路径（必须已存在）
        transform: 接收当前文件内容，返回新内容
    """
    if not filepath.exists():
        raise FileNotFoundError(f"文件不存在，无法原子更新: {filepath}")

    current = filepath.read_text(encoding="utf-8")

    # 如果多进程同时写，这里存在 read-check-then-write 竞争。
    # 个人单用户场景下概率极低，暂不做文件锁。如有需要可加 fcntl.flock。
    new_content = transform(current)
    atomic_write(filepath, new_content)
