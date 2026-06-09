"""助理数据模型 — Todo/Reminder/Note/Bookmark/Habit.

继承 memory/models.py 的 uuid7/now_iso 工具函数。
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Any
from knowledge_wiki.memory.models import uuid7, now_iso


def _json_dumps(obj: list) -> str:
    """序列化列表为 JSON 字符串."""
    return json.dumps(obj, ensure_ascii=False)


def _json_loads(val: Any) -> list:
    """安全解析 JSON 字符串为列表."""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
    return val if isinstance(val, list) else []


# ============================================================================
# Todo — 待办事项
# ============================================================================

@dataclass
class Todo:
    """待办事项."""
    id: str = field(default_factory=uuid7)
    title: str = ""
    description: str = ""
    status: str = "pending"      # pending|in_progress|done|cancelled
    priority: str = "medium"      # high|medium|low
    deadline: str | None = None
    completed_at: str | None = None
    tags: list[str] = field(default_factory=list)
    source: str = "wecom"
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def from_row(cls, row: Any) -> "Todo":
        d = dict(row)
        d["tags"] = _json_loads(d.get("tags", "[]"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tags"] = _json_dumps(self.tags)
        return d


# ============================================================================
# Reminder — 定时提醒
# ============================================================================

@dataclass
class Reminder:
    """定时提醒."""
    id: str = field(default_factory=uuid7)
    todo_id: str | None = None
    content: str = ""
    trigger_at: str = ""
    repeat_rule: str | None = None   # cron 表达式
    status: str = "active"            # active|fired|cancelled
    fired_at: str | None = None
    user_id: str = ""                 # 企微 UserID（用于主动推送）
    created_at: str = field(default_factory=now_iso)

    @classmethod
    def from_row(cls, row: Any) -> "Reminder":
        d = dict(row)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# Note — 快速笔记
# ============================================================================

@dataclass
class Note:
    """快速笔记."""
    id: str = field(default_factory=uuid7)
    content: str = ""
    tags: list[str] = field(default_factory=list)
    related_page: str = ""           # [[wiki page]]
    source: str = "wecom"
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def from_row(cls, row: Any) -> "Note":
        d = dict(row)
        d["tags"] = _json_loads(d.get("tags", "[]"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tags"] = _json_dumps(self.tags)
        return d


# ============================================================================
# Bookmark — 书签
# ============================================================================

@dataclass
class Bookmark:
    """书签."""
    id: str = field(default_factory=uuid7)
    url: str = ""
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    read_status: str = "unread"      # unread|reading|read
    ingested: int = 0                # 0|1
    wiki_page: str = ""
    created_at: str = field(default_factory=now_iso)

    @classmethod
    def from_row(cls, row: Any) -> "Bookmark":
        d = dict(row)
        d["tags"] = _json_loads(d.get("tags", "[]"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tags"] = _json_dumps(self.tags)
        return d


# ============================================================================
# Habit + HabitLog — 习惯追踪
# ============================================================================

@dataclass
class Habit:
    """习惯定义."""
    id: str = field(default_factory=uuid7)
    name: str = ""
    unit: str = "boolean"            # boolean|count|duration
    target: float | None = None
    created_at: str = field(default_factory=now_iso)
    archived_at: str | None = None   # NULL = 活跃中

    @classmethod
    def from_row(cls, row: Any) -> "Habit":
        d = dict(row)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HabitLog:
    """习惯打卡记录."""
    id: str = field(default_factory=uuid7)
    habit_id: str = ""
    date: str = ""                   # YYYY-MM-DD
    value: float = 0.0
    note: str = ""

    @classmethod
    def from_row(cls, row: Any) -> "HabitLog":
        d = dict(row)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)
