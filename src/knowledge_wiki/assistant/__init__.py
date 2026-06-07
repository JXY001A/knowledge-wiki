"""个人 AI 助手模块 — Track B：基础设施 + 数据结构.

双层存储架构：
    文件系统（wiki/*.md） — 知识内容
    SQLite（wiki/.data/assistant.db） — 助理结构化数据（待办/提醒/笔记/书签/习惯）

模块：
    db.py        — SQLite 连接 + schema 迁移
    models/      — 数据模型（Todo/Reminder/Note/Bookmark/Habit）
    scheduler.py — APScheduler 定时任务
    backup.py    — SQL dump + 文件快照
    push.py      — 企微主动推送（待实现）
"""

from knowledge_wiki.assistant.db import get_db, init_schema

__all__ = ["get_db", "init_schema"]
