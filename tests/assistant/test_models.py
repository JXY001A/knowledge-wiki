"""assistant 数据模型单元测试 — Todo/Reminder/Note/Bookmark/Habit/HabitLog."""

import json
from knowledge_wiki.assistant.models import (
    Todo, Reminder, Note, Bookmark, Habit, HabitLog,
)


class TestTodo:
    """待办事项模型."""

    def test_default_values(self):
        t = Todo(title="测试待办")
        assert t.title == "测试待办"
        assert t.status == "pending"
        assert t.priority == "medium"
        assert isinstance(t.tags, list)
        assert len(t.id) > 0

    def test_to_dict_tags_serialized(self):
        t = Todo(title="买菜", tags=["生活", "急"], priority="high")
        d = t.to_dict()
        assert d["title"] == "买菜"
        assert d["priority"] == "high"
        assert isinstance(d["tags"], str)
        assert "生活" in d["tags"]

    def test_from_row_parses_tags(self):
        row = {
            "id": "abc", "title": "阅读", "description": "",
            "status": "pending", "priority": "low", "deadline": None,
            "completed_at": None, "tags": '["学习","每日"]', "source": "wecom",
            "created_at": "2026-06-01", "updated_at": "2026-06-01",
        }
        t = Todo.from_row(row)
        assert t.tags == ["学习", "每日"]
        assert t.title == "阅读"

    def test_from_row_handles_non_json_tags(self):
        row = {
            "id": "x", "title": "x", "description": "",
            "status": "pending", "priority": "medium", "deadline": None,
            "completed_at": None, "tags": None, "source": "wecom",
            "created_at": "x", "updated_at": "x",
        }
        t = Todo.from_row(row)
        assert t.tags == []

    def test_uuid7_unique_per_instance(self):
        t1 = Todo(title="a")
        t2 = Todo(title="b")
        assert t1.id != t2.id


class TestReminder:
    """定时提醒模型."""

    def test_default_values(self):
        r = Reminder(content="开会提醒", trigger_at="2026-06-08T10:00")
        assert r.content == "开会提醒"
        assert r.status == "active"
        assert r.repeat_rule is None

    def test_to_dict_roundtrip(self):
        r = Reminder(
            content="喝水", trigger_at="2026-06-08T14:00",
            repeat_rule="0 14 * * *", user_id="user123",
        )
        d = r.to_dict()
        assert d["content"] == "喝水"
        assert d["repeat_rule"] == "0 14 * * *"
        assert d["user_id"] == "user123"

    def test_from_row(self):
        row = {
            "id": "r1", "todo_id": None, "content": "测试",
            "trigger_at": "2026-06-01T08:00", "repeat_rule": None,
            "status": "active", "fired_at": None, "user_id": "",
            "created_at": "2026-06-01",
        }
        r = Reminder.from_row(row)
        assert r.content == "测试"
        assert r.trigger_at == "2026-06-01T08:00"


class TestNote:
    """快速笔记模型."""

    def test_default_values(self):
        n = Note(content="今天学了 MCP 协议")
        assert n.content == "今天学了 MCP 协议"
        assert n.source == "wecom"
        assert n.related_page == ""

    def test_tags_serialization(self):
        n = Note(content="x", tags=["MCP", "协议"])
        d = n.to_dict()
        assert isinstance(d["tags"], str)
        parsed = json.loads(d["tags"])
        assert parsed == ["MCP", "协议"]

    def test_from_row_parses_tags(self):
        row = {
            "id": "n1", "content": "笔记内容", "tags": '["tag1"]',
            "related_page": "", "source": "mcp",
            "created_at": "2026-06-01", "updated_at": "2026-06-01",
        }
        n = Note.from_row(row)
        assert n.tags == ["tag1"]


class TestBookmark:
    """书签模型."""

    def test_default_values(self):
        b = Bookmark(url="https://example.com", title="示例")
        assert b.url == "https://example.com"
        assert b.read_status == "unread"
        assert b.ingested == 0

    def test_to_dict(self):
        b = Bookmark(
            url="https://test.com", title="Test",
            tags=["参考"], read_status="read",
        )
        d = b.to_dict()
        assert d["url"] == "https://test.com"
        assert d["read_status"] == "read"

    def test_from_row(self):
        row = {
            "id": "b1", "url": "https://x.com", "title": "X",
            "description": "desc", "tags": '["a"]', "read_status": "unread",
            "ingested": 0, "wiki_page": "", "created_at": "2026-06-01",
        }
        b = Bookmark.from_row(row)
        assert b.url == "https://x.com"
        assert b.tags == ["a"]


class TestHabit:
    """习惯模型."""

    def test_default_unit(self):
        h = Habit(name="喝水")
        assert h.unit == "boolean"
        assert h.target is None
        assert h.archived_at is None

    def test_to_dict(self):
        h = Habit(name="跑步", unit="count", target=5.0)
        d = h.to_dict()
        assert d["name"] == "跑步"
        assert d["unit"] == "count"
        assert d["target"] == 5.0

    def test_from_row(self):
        row = {
            "id": "h1", "name": "冥想", "unit": "duration",
            "target": 10.0, "created_at": "2026-06-01", "archived_at": None,
        }
        h = Habit.from_row(row)
        assert h.name == "冥想"
        assert h.unit == "duration"
        assert h.target == 10.0


class TestHabitLog:
    """习惯打卡记录模型."""

    def test_default_values(self):
        hl = HabitLog(habit_id="h1", date="2026-06-08")
        assert hl.value == 0.0
        assert hl.note == ""

    def test_to_dict(self):
        hl = HabitLog(habit_id="h1", date="2026-06-08", value=1.0, note="完成")
        d = hl.to_dict()
        assert d["value"] == 1.0
        assert d["note"] == "完成"
