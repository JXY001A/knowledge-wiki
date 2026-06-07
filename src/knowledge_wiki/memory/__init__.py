"""记忆系统模块.— Phase 3：记忆系统.

提供结构化操作日志、会话上下文、用户画像和语义记忆增强。
所有模块围绕 MemoryStore 单例协调工作。

模块：
    db.py      — SQLite 连接 + schema 迁移
    models.py  — 数据模型（EpisodicRecord 等）
    writer.py  — 结构化日志写入（文件 + SQLite 双写）
    reader.py  — 结构化查询 API
    working.py — 会话上下文提取与压缩
    profile.py — 用户画像自动生成
    semantic.py— 语义记忆增强（概念覆盖度分析）
"""

from knowledge_wiki.memory.db import get_db, init_schema
from knowledge_wiki.memory.models import EpisodicRecord
from knowledge_wiki.memory.writer import record_event, record_query, record_ingest, record_lint
from knowledge_wiki.memory.reader import recent_events, search_memory, get_stats

__all__ = [
    "get_db",
    "init_schema",
    "EpisodicRecord",
    "record_event",
    "record_query",
    "record_ingest",
    "record_lint",
    "recent_events",
    "search_memory",
    "get_stats",
]
