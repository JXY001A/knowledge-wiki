"""记忆数据模型 — EpisodicRecord 及子类型."""

import json
import uuid
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def uuid7() -> str:
    """生成 UUID7（时间有序的 UUID），用于数据库主键.

    UUID7 = 48-bit Unix ms timestamp + 74-bit random
    时间前缀保证插入 B-tree 索引时是追加而非随机插入，
    比 UUID4 在 SQLite 上的写入性能好 3-5x。
    """
    # 48-bit timestamp（毫秒）
    ms = int(time.time() * 1000)
    timestamp_hex = f"{ms:012x}"  # 6 bytes = 12 hex chars

    # 74-bit random（版本 7 标记 + 随机后缀）
    import os
    rand = os.urandom(10)  # 10 bytes
    # Set version (7) and variant (10xx)
    ver_byte = (rand[0] & 0x0F) | 0x70
    var_byte = (rand[1] & 0x3F) | 0x80
    rand_part = bytes([ver_byte, var_byte]) + rand[2:]

    return f"{timestamp_hex[:8]}-{timestamp_hex[8:12]}-7{rand_part[:2].hex()}-{rand_part[2:4].hex()}-{rand_part[4:].hex()}"


def now_iso() -> str:
    """返回当前 UTC 时间的 ISO8601 字符串."""
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# 主数据模型
# ============================================================================


@dataclass
class EpisodicRecord:
    """一条情景记忆记录 — 对应 memory_events 表的一行.

    表示一次操作事件的完整结构化记录：谁、何时、做了什么、涉及哪些知识。
    """

    # 核心字段
    id: str = field(default_factory=uuid7)
    event_type: str = ""  # 'query' | 'ingest' | 'lint' | 'note' | 'system' | 'synthesis'

    # 内容字段
    summary: str = ""  # 一句话摘要
    details: str = ""  # 详细内容（markdown）

    # 知识关联
    pages: list[str] = field(default_factory=list)  # 涉及的 wiki 页面
    concepts: list[str] = field(default_factory=list)  # 涉及的概念

    # 元数据
    score: int | None = None  # 自评分（1-5）
    user_id: str = ""  # 触发用户
    source: str = "unknown"  # 'wecom' | 'mcp' | 'cli' | 'auto'
    domain: str = ""  # 知识领域
    tags: list[str] = field(default_factory=list)  # 标签
    created_at: str = field(default_factory=now_iso)

    # ---- 序列化 ----

    @classmethod
    def from_row(cls, row: Any) -> "EpisodicRecord":
        """从 sqlite3.Row 构造 EpisodicRecord."""
        d = dict(row)
        for field_name in ["pages", "concepts", "tags"]:
            val = d.get(field_name, "[]")
            if isinstance(val, str):
                try:
                    d[field_name] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[field_name] = []
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        """转为字典，JSON 字段序列化为字符串."""
        d = asdict(self)
        for field_name in ["pages", "concepts", "tags"]:
            d[field_name] = json.dumps(d[field_name], ensure_ascii=False)
        return d

    def to_markdown(self) -> str:
        """生成人类可读的 markdown 日志条目."""
        lines = [f"## [{self._date_str()}] {self.event_type} | {self.summary}", ""]
        if self.domain:
            lines.append(f"- 领域：{self.domain}")
        if self.pages:
            links = "、".join(f"[[{p}]]" for p in self.pages)
            lines.append(f"- 涉及页面：{links}")
        if self.concepts:
            lines.append(f"- 涉及概念：{', '.join(self.concepts)}")
        if self.score:
            lines.append(f"- 评分：{'⭐' * self.score}")
        if self.details:
            lines.append(f"\n{self.details}")
        lines.append("")
        return "\n".join(lines)

    def _date_str(self) -> str:
        """提取日期部分."""
        return self.created_at[:10] if self.created_at else "unknown"
