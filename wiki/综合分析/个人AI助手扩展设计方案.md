---
title: 个人AI助手扩展设计方案
type: synthesis
tags: [知识工程, Agent, 架构, 方案, 数据工程]
created: 2026-06-06
updated: 2026-06-06
sources:
  - "[[知识库系统全链路架构]]"
  - "[[AI 自进化知识系统 — 建设路线图]]"
  - "[[知识库系统工程化架构]]"
  - "[[Agent Skills体系]]"
  - "[[Skill 设计模式（Google 5种）]]"
confidence: medium
---

> 在现有 knowledge-wiki 基础设施之上，扩展个人 AI 助理能力（定时任务、待办提醒、笔记、书签、习惯追踪等），采用“文件系统 + SQLite”双层存储、Skill 插件式功能扩展的架构方案。

## 一、设计目标

| 目标 | 说明 |
|------|------|
| **零运维负担** | 无需额外数据库进程、无需第三方服务，所有依赖 Python 标准库 + SQLite |
| **增量扩展** | 不改动已有模块，新能力以 Skill（skill.json + impl.py）形式注入 |
| **数据不丢** | 原子写入 + Git 远程备份 + SQLite 定时 dump + 本地快照，四层保障 |
| **双入口统一** | 企微 Bot（移动端）+ MCP Server（AI CLI 工具），共享同一套数据 |
| **个人规模优先** | 不引入分布式/多用户设计，专注单用户 10 年 5-10 万条数据的极致体验 |

## 二、现状基线

### 已具备

| 能力 | 实现 | 代码位置 |
|------|------|----------|
| 知识摄入 | 企微 URL → LLM 分析 → wiki 页面生成 | `webhook/process.py` |
| 知识检索 | catalog → BM25 → layered 四阶段流水线 | `wiki/retrieval/pipeline.py` |
| MCP Server | 6 个工具注册（search/query/ingest/lint/skill-list/skill-execute） | `mcp/server.py` |
| 企微 Bot | 消息接收、解密、路由分发、markdown 回复 | `webhook/app.py` |
| Skill 引擎 | 文件系统注册表 + 3 级渐进加载 + 意图匹配 + impl 执行 | `skill/` |
| LLM 双通道 | DeepSeek API（ingest 分析） + Ollama 本地（webhook 回答） | `llm/` |
| Git 同步 | 每次操作自动 add/commit/push | `wiki/git.py` |
| 运行环境 | DevMechin 7×24 常驻，systemd 管理 | `deploy/` |

### 待补齐

| 缺口 | 影响 |
|------|------|
| 无调度器 | 无法执行定时任务、无法主动推送 |
| 无结构化数据存储 | 待办/提醒/笔记查询只能扫文件，效率低 |
| 数据写入无原子保护 | 断电/崩溃可能导致文件损坏 |
| Git push 静默吞异常 | 网络故障时数据滞留本地且无告警 |
| 企微只能被动回复 | 用户不发消息就无法收到任何提醒 |

## 三、整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    入口层                                │
│                                                         │
│  kw-server serve      kw-server webhook   kw-server scheduler │
│  (已有 :9300)          (已有 :9400)         (新增子命令)   │
│       │                     │                    │        │
└───────┼─────────────────────┼────────────────────┼────────┘
        │                     │                    │
┌───────▼─────────────────────▼────────────────────▼────────┐
│                      Skill 引擎（已有 5 → 新增 6）         │
│                                                          │
│  Tier 1（始终加载）:  ingest-article / query-knowledge     │
│                      search-wiki / save-note              │
│                      todo-manage / remind-set      ← 新增 │
│  Tier 2（按需加载）:  lint-wiki / note-quick        ← 新增 │
│                      schedule-view / daily-brief   ← 新增 │
│                                                          │
└───────┬──────────────────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────────────────┐
│                    assistant/ 新模块                       │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │scheduler │ │  models  │ │  backup  │ │  push    │   │
│  │APScheduler│ │todo/remind│ │快照+dump │ │企微主动推│   │
│  └────┬─────┘ │/note/book│ └────┬─────┘ └────┬─────┘   │
│       │       │ /habit    │      │           │          │
│       │       └────┬─────┘      │           │          │
│       │            │            │           │          │
│  ┌────▼────────────▼────────────▼───────────▼───────┐  │
│  │                    db.py                         │  │
│  │  SQLite 连接池 / schema 迁移 / 事务管理           │  │
│  └────────────────────────┬─────────────────────────┘  │
└───────────────────────────┼─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  文件存储     │  │  SQLite 存储  │  │  .cache/     │
│              │  │              │  │              │
│ wiki/        │  │ wiki/.data/  │  │ 检索索引     │
│ raw/         │  │ assistant.db │  │ 调度器状态   │
│ 知识内容     │  │ 助理结构化数据│  │ LLM 缓存     │
│ Git 版本控制 │  │ SQL dump→Git │  │ 可重建       │
└──────────────┘  └──────────────┘  └──────────────┘
```

## 四、双层存储设计

### 4.1 存储分工

```
┌─────────────────────────────────────────────────────┐
│              文件系统（Markdown + Git）               │
│                                                     │
│  ✅ 资料摘要、概念页、综合分析、日报                  │
│  ✅ 领域知识、技术文档（> 500 字）                    │
│  ✅ 需要 Obsidian 打开浏览的内容                      │
│  ✅ 需要版本历史追溯的内容                            │
│                                                     │
├─────────────────────────────────────────────────────┤
│                SQLite（wiki/.data/assistant.db）     │
│                                                     │
│  ✅ 待办事项（频繁状态变更、条件筛选）                │
│  ✅ 定时提醒（时间触发、重复规则）                    │
│  ✅ 短笔记（< 200 字、全文搜索）                     │
│  ✅ 书签（结构化、去重、阅读状态）                    │
│  ✅ 习惯追踪（数值型、时间序列聚合）                  │
│  ✅ 消息发送队列（重试状态跟踪）                      │
│                                                     │
├─────────────────────────────────────────────────────┤
│                .cache/（可重建、不入 Git）            │
│                                                     │
│  ✅ BM25 检索索引（zstd 压缩 pickle）                │
│  ✅ APScheduler job store（SQLite 文件）             │
│  ✅ LLM API 响应缓存                                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 4.2 为什么 SQLite

| 考量 | 结论 |
|------|------|
| **部署** | Python 标准库自带 `sqlite3`，零依赖，apt/brew 什么都不用装 |
| **运维** | 单文件 `assistant.db`，备份就是 `cp` |
| **性能** | 个人 10 年约 5 万条数据，远未到 SQLite 瓶颈（百万行起才需优化） |
| **与现有栈的关系** | APScheduler 的 SQLiteJobStore 本来就依赖 SQLite，不引入新概念 |
| **Git 集成** | 定期 `.dump` 到 SQL 文本文件，进入 Git 版本控制，diff 可读 |

### 4.3 数据规模预估

| 数据类型 | 日均新增 | 月均 | 年均 | 10 年 |
|----------|:-------:|:----:|:----:|:-----:|
| 待办事项 | 5-10 | 200 | 2,500 | 25,000 |
| 定时提醒 | 1-3 | 40 | 500 | 5,000 |
| 快速笔记 | 2-5 | 100 | 1,200 | 12,000 |
| 书签 | 1-3 | 40 | 500 | 5,000 |
| 习惯日志 | 1-3 | 40 | 500 | 5,000 |
| **合计** | **~20** | **~420** | **~5,200** | **~52,000** |

SQLite 单表百万行以内无需任何优化，当前规模完全不需要考虑分库分表。

## 五、数据库模型

### 5.1 表结构

```sql
-- ============================================================
-- 待办事项
-- ============================================================
CREATE TABLE todos (
    id          TEXT PRIMARY KEY,              -- UUID7（时间有序）
    title       TEXT NOT NULL,                 -- 标题
    description TEXT,                          -- 详细描述（markdown）
    status      TEXT NOT NULL DEFAULT 'pending', -- pending|in_progress|done|cancelled
    priority    TEXT NOT NULL DEFAULT 'medium',  -- high|medium|low
    deadline    TEXT,                          -- ISO8601: "2026-06-07T18:00:00+08:00"
    completed_at TEXT,
    tags        TEXT NOT NULL DEFAULT '[]',     -- JSON array: ["工作","项目X"]
    source      TEXT DEFAULT 'wecom',          -- wecom|mcp|cli|auto
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX idx_todos_status ON todos(status);
CREATE INDEX idx_todos_deadline ON todos(deadline);
CREATE INDEX idx_todos_priority ON todos(priority);
CREATE INDEX idx_todos_created ON todos(created_at);

-- ============================================================
-- 定时提醒（独立于 todos，也可关联）
-- ============================================================
CREATE TABLE reminders (
    id          TEXT PRIMARY KEY,              -- UUID7
    todo_id     TEXT,                          -- 关联待办（可选）
    content     TEXT NOT NULL,                 -- 提醒内容
    trigger_at  TEXT NOT NULL,                 -- 触发时间 ISO8601
    repeat_rule TEXT,                          -- cron 表达式："0 9 * * 1-5"
    status      TEXT NOT NULL DEFAULT 'active',-- active|fired|cancelled
    fired_at    TEXT,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (todo_id) REFERENCES todos(id) ON DELETE SET NULL
);

CREATE INDEX idx_reminders_trigger ON reminders(trigger_at, status);

-- ============================================================
-- 快速笔记（短文本，面向闪念捕获）
-- ============================================================
CREATE TABLE notes (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    related_page TEXT,                         -- wiki 页面引用：[[知识库系统全链路架构]]
    source      TEXT DEFAULT 'wecom',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- FTS5 全文搜索（中文分词依赖 jieba 预处理）
CREATE VIRTUAL TABLE notes_fts USING fts5(
    content, tags, content=notes, content_rowid=rowid
);

-- 触发器：自动同步 notes → notes_fts
CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
END;
CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content, tags) VALUES ('delete', old.rowid, old.content, old.tags);
END;
CREATE TRIGGER notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content, tags) VALUES ('delete', old.rowid, old.content, old.tags);
    INSERT INTO notes_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
END;

-- ============================================================
-- 书签
-- ============================================================
CREATE TABLE bookmarks (
    id          TEXT PRIMARY KEY,
    url         TEXT NOT NULL UNIQUE,
    title       TEXT,
    description TEXT,
    tags        TEXT NOT NULL DEFAULT '[]',
    read_status TEXT DEFAULT 'unread',         -- unread|reading|read
    ingested    INTEGER DEFAULT 0,             -- 是否已转为 wiki 资料摘要
    wiki_page   TEXT,                          -- 关联的 wiki 页面名
    created_at  TEXT NOT NULL
);

CREATE INDEX idx_bookmarks_status ON bookmarks(read_status);

-- ============================================================
-- 习惯追踪
-- ============================================================
CREATE TABLE habits (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,                 -- 习惯名："每天喝水"
    unit        TEXT DEFAULT 'boolean',        -- boolean|count|duration
    target      REAL,                          -- 目标值（boolean 型恒为 1）
    created_at  TEXT NOT NULL,
    archived_at TEXT                           -- NULL = 活跃中
);

CREATE TABLE habit_logs (
    id          TEXT PRIMARY KEY,
    habit_id    TEXT NOT NULL,
    date        TEXT NOT NULL,                 -- YYYY-MM-DD
    value       REAL NOT NULL,
    note        TEXT,
    FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE,
    UNIQUE(habit_id, date)
);

CREATE INDEX idx_habit_logs_date ON habit_logs(date);
CREATE INDEX idx_habit_logs_habit ON habit_logs(habit_id, date);

-- ============================================================
-- 消息推送队列（失败重试）
-- ============================================================
CREATE TABLE push_queue (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    content     TEXT NOT NULL,
    msg_type    TEXT DEFAULT 'markdown',       -- markdown|text|template_card
    status      TEXT DEFAULT 'pending',        -- pending|sent|failed
    retries     INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    last_error  TEXT,
    created_at  TEXT NOT NULL,
    next_retry_at TEXT
);

CREATE INDEX idx_push_queue_next ON push_queue(next_retry_at, status);

-- ============================================================
-- Schema 版本管理（迁移追踪）
-- ============================================================
CREATE TABLE schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL,
    description TEXT
);
```

### 5.2 数据模型（Python dataclass → SQL row）

```python
# assistant/models/todo.py
@dataclass
class Todo:
    """待办事项数据模型"""
    id: str          # UUID7
    title: str
    description: str = ""
    status: str = "pending"      # pending|in_progress|done|cancelled
    priority: str = "medium"      # high|medium|low
    deadline: str | None = None
    completed_at: str | None = None
    tags: list[str] = field(default_factory=list)  # JSON 序列化
    source: str = "wecom"
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Todo":
        d = dict(row)
        d["tags"] = json.loads(d.get("tags", "[]"))
        return cls(**d)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tags"] = json.dumps(self.tags, ensure_ascii=False)
        return d
```

### 5.3 SQLite 连接管理

```python
# assistant/db.py
import sqlite3
from pathlib import Path
from knowledge_wiki.config import settings

DB_PATH = settings.wiki_root / "wiki" / ".data" / "assistant.db"

def get_db() -> sqlite3.Connection:
    """获取数据库连接（自动启用 WAL 模式和外键约束）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")       # 写不阻塞读
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_schema(conn: sqlite3.Connection) -> None:
    """初始化或迁移 schema"""
    current_ver = conn.execute(
        "SELECT MAX(version) FROM schema_version"
    ).fetchone()[0] or 0

    # 迁移脚本列表：[版本号, SQL, 描述]
    migrations = [
        (1, SCHEMA_V1, "初始 schema：todos/reminders/notes/bookmarks/habits/push_queue"),
        # 未来迁移按版本号递增
    ]

    for ver, sql, desc in migrations:
        if ver > current_ver:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                [ver, datetime.now().isoformat(), desc]
            )
    conn.commit()
```

## 六、持久化与备份策略

### 6.1 六层保障

```
Layer 1: 原子写入
    └─ 所有文件写入用 tmp + os.replace，SQLite 自带 atomic commit

Layer 2: WAL 日志
    └─ SQLite WAL 模式：崩溃后自动从 WAL 恢复未完成的事务

Layer 3: 本地快照
    └─ 每日凌晨 tar czf 备份 wiki/ + raw/，保留 7 天

Layer 4: SQL dump
    └─ 每日凌晨 sqlite3 .dump → SQL 文本文件，存入 raw/assets/db-backup/

Layer 5: Git 推送
    └─ 每次操作后 commit_and_push，失败进重试队列

Layer 6: GitHub 远程
    └─ 最终备份，git clone 即可完整恢复
```

### 6.2 恢复流程

```
☠️ 灾难：DevMechin 磁盘损坏

恢复步骤：
  1. git clone https://github.com/xxx/knowledge-wiki.git  ← 恢复所有文件
  2. cp raw/assets/db-backup/assistant-2026-06-06.sql .    ← 取最近 dump
  3. sqlite3 wiki/.data/assistant.db < assistant-*.sql      ← 重建数据库
  4. kw-server db migrate                                  ← 执行增量迁移
  5. kw-server scheduler                                    ← 启动调度器
     └─ 启动时扫描 wiki/日程/ + db.reminders，补注册未过期的提醒

预期数据损失：
  - Wiki 页面：0（Git 有完整历史）
  - 助理数据：最多丢失当天（上次 dump 至今的数据），约 20 条
    └─ 如企微有消息记录，可从聊天记录补录
```

### 6.3 备份调度

| 动作 | 频率 | 方式 |
|------|------|------|
| Git push | 每次写操作 | `commit_and_push()`（改进版：带重试） |
| SQL dump | 每天 02:00 | `sqlite3 .dump` → `raw/assets/db-backup/assistant-YYYY-MM-DD.sql` |
| 文件快照 | 每天 03:00 | `tar czf backup/wiki-YYYYMMDD.tar.gz wiki/ raw/`，保留 7 天 |
| 完整性校验 | 每周日 04:00 | 校验 SQLite integrity_check + frontmatter 合法性 |

## 七、New Skills 设计

### 7.1 技能清单

| 技能名 | Tier | 模型 | 触发词 | 核心能力 |
|--------|:---:|------|--------|----------|
| `todo-manage` | 1 | local | 待办/todo/任务/完成 | 自然语言 → 待办 CRUD |
| `remind-set` | 1 | local | 提醒/闹钟/定时 | 自然语言 → 定时提醒 |
| `note-quick` | 1 | local | 笔记/记一下/备忘 | 快速文本捕获+自动标签 |
| `bookmark-save` | 2 | local | 收藏/书签/稍后读 | URL 保存+元数据提取 |
| `schedule-view` | 2 | local | 日程/今天/明天 | 今日待办+提醒汇总 |
| `daily-brief` | 2 | local | 日报/早报/晚报 | 自动生成每日简报 |
| `habit-track` | 3 | local | 打卡/习惯 | 记录+统计习惯完成情况 |

### 7.2 技能示例：todo-manage

```
skills/todo-manage/
├── skill.json
├── SKILL.md
└── impl.py
```

**skill.json**：
```json
{
  "name": "todo-manage",
  "version": "1.0",
  "description": "管理待办事项：创建、查看、完成、删除",
  "tier": 1,
  "model": "local",
  "tools": ["todo_list", "todo_create", "todo_complete"],
  "triggers": ["待办", "todo", "任务", "完成", "取消任务"],
  "dependencies": []
}
```

**impl.py** 核心逻辑：
```python
def execute(ctx: dict) -> str:
    """待办管理入口。Ollama 做意图分类 → 路由到具体操作。"""
    intent_text = ctx.get("input_text", "")
    user_id = ctx.get("user_id", "")
    send_md = ctx.get("send_md")  # 企微回复回调

    # 1. 用本地 Ollama 做意图分类（轻量，~0.5s）
    action = classify_intent(intent_text)
    # → {action: "create", title: "提交Q2报告", priority: "high", deadline: "2026-06-07"}

    # 2. 路由到具体操作
    if action["action"] == "create":
        todo = todo_create(**action)
        send_md(user_id, f"✅ 已创建待办：{todo.title} [{todo.priority}]")

    elif action["action"] == "list":
        todos = todo_list(status="pending")
        # 格式化待办列表...

    elif action["action"] == "complete":
        # 模糊匹配标题 → 标记 done
        ...
```

### 7.3 技能示例：daily-brief

```
# 早报结构（每天 08:00 自动推送）
📋 2026-06-06 早报

**今日待办** (3 项)
🔴 提交Q2报告 [截止:今天]
🟡 代码review [15:00]
🟢 更新知识库

**今日提醒**
⏰ 10:00 团队站会
⏰ 15:00 code review

**知识库动态**
- 新增：资料摘要：Claude Code 最佳实践
- 更新：概念/MCP（Model Context Protocol）

---
# 晚报结构（每天 21:00 自动推送）
📋 2026-06-06 晚报

**今日完成** (2 项)
✅ 提交Q2报告
✅ 代码review

**未完成** (1 项)
⏳ 更新知识库

**今日笔记** (2 条)
- 部署脚本需要加 health check 超时
- MCP Server 的 DNS rebinding 配置梳理

**习惯打卡**
💧 喝水 6/8 杯
🏃 跑步 30min ✅
```

## 八、新增 MCP 工具

| 工具名 | 参数 | 返回 | 类型 |
|--------|------|------|------|
| `todo_list` | status, priority, deadline_before, limit | 待办列表（JSON→Markdown） | 查询 |
| `todo_create` | title, priority?, deadline?, tags? | 创建的待办 | 写入 |
| `todo_complete` | todo_id | 完成确认 | 写入 |
| `remind_set` | content, trigger_at, repeat_rule? | 提醒确认 | 写入 |
| `remind_list` | status | 活跃提醒列表 | 查询 |
| `note_create` | content, tags? | 笔记确认 | 写入 |
| `note_search` | query, limit | 匹配笔记 | 查询 |
| `bookmark_add` | url, tags? | 书签确认 | 写入 |
| `bookmark_list` | read_status, tags? | 书签列表 | 查询 |
| `daily_brief` | user_id | 早报/晚报 markdown | 查询 |
| `schedule_today` | user_id | 今日日程+待办+提醒 | 查询 |
| `habit_create` | name, unit, target? | 习惯确认 | 写入 |
| `habit_log` | habit_name, value | 打卡确认 | 写入 |
| `habit_stats` | habit_name? | 完成统计 | 查询 |

这些工具使外部 AI（Claude Code 等）能直接操作助理数据，而不需要通过企微 Bot。

## 九、调度器设计

### 9.1 核心组件

```python
# assistant/scheduler.py

from apscheduler import AsyncIOScheduler
from apscheduler.jobstores.sqlite import SQLiteJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(
        jobstores={
            'default': SQLiteJobStore(
                url=f'sqlite:///{DB_PATH}',
                tablename='apscheduler_jobs'
            )
        },
        timezone='Asia/Shanghai'
    )

    # ---- 系统预置 Job ----
    # 早报
    scheduler.add_job(
        send_morning_brief,
        CronTrigger(hour=8, minute=0),
        id='system:daily-brief:morning',
        name='早报推送',
        replace_existing=True,
    )
    # 晚报
    scheduler.add_job(
        send_evening_brief,
        CronTrigger(hour=21, minute=0),
        id='system:daily-brief:evening',
        name='晚报推送',
        replace_existing=True,
    )
    # SQL dump 备份
    scheduler.add_job(
        backup_database,
        CronTrigger(hour=2, minute=17),  # 非整点，避免与其他任务碰撞
        id='system:backup:db-dump',
        replace_existing=True,
    )
    # 文件快照
    scheduler.add_job(
        backup_files,
        CronTrigger(hour=3, minute=13),
        id='system:backup:file-snapshot',
        replace_existing=True,
    )
    # 推送重试
    scheduler.add_job(
        retry_push_queue,
        CronTrigger(minute='*/5'),
        id='system:push:retry',
        replace_existing=True,
    )
    # 待办到期扫描
    scheduler.add_job(
        scan_deadline_reminders,
        CronTrigger(minute=7),  # 每小时一次
        id='system:remind:deadline-scan',
        replace_existing=True,
    )

    return scheduler
```

### 9.2 启动后恢复

```python
async def recover_reminders(scheduler, db):
    """启动时扫描数据库，补注册所有未过期的提醒"""
    now = datetime.now().isoformat()
    active = db.execute(
        "SELECT * FROM reminders WHERE status='active' AND trigger_at > ?",
        [now]
    ).fetchall()

    restored = 0
    for r in active:
        job_id = f"remind:{r['id']}"
        if not scheduler.get_job(job_id):
            scheduler.add_job(
                fire_reminder,  # 触发函数
                DateTrigger(run_date=r['trigger_at']),
                id=job_id,
                kwargs={'reminder_id': r['id']},
                replace_existing=True,
            )
            restored += 1

    if restored > 0:
        print(f"[scheduler] 恢复 {restored} 个提醒", flush=True)
```

### 9.3 新增 CLI 子命令

```bash
# 调度器独立进程
kw-server scheduler

# 数据库管理
kw-server db init       # 初始化 schema
kw-server db migrate    # 执行迁移
kw-server db backup     # 手动 dump
kw-server db stats      # 数据统计
```

## 十、实施路线

### Phase 1：基础设施（2-3 天）

```
目标：数据库就位 + 调度器运行

□ pyproject.toml 添加 apscheduler 依赖
□ 实现 assistant/db.py（连接管理 + schema 迁移）
□ 实现 assistant/models/（Todo/Reminder/Note/Bookmark/Habit 数据模型）
□ 实现 assistant/scheduler.py（APScheduler 启动 + 系统预置 Job）
□ 实现 assistant/backup.py（SQL dump + 文件快照）
□ 改造 wiki/git.py commit_and_push（去静默 + 重试队列）
□ 新增 wiki/atomic.py（原子写入封装）
□ 扩展现有写入路径（builder/paths）使用原子写入
□ 扩展 CLI：kw-server scheduler / db 子命令
□ 新增 wiki/.data/ 目录（.gitignore 中排除 *.db，保留 *.sql dump）
```

### Phase 2：核心技能（3-4 天）

```
目标：6 个新技能可用，企微 Bot 可交互

□ todo-manage 技能（自然语言解析 → sqlite CRUD → 回复）
□ remind-set 技能（时间解析 → sqlite + apscheduler job 双写）
□ note-quick 技能（文本存储 + FTS5 搜索 + 自动标签）
□ bookmark-save 技能（URL 解析 + 元数据提取 + 去重）
□ schedule-view 技能（今日汇总查询）
□ 注册 14 个 MCP 工具到 MCP Server
```

### Phase 3：自动化（2-3 天）

```
目标：早报/晚报自动推送，全流程闭环

□ daily-brief 技能（早报 + 晚报内容生成）
□ habit-track 技能（打卡 + 统计）
□ 企微主动推送通道（push.py 封装 wechat/api.py）
□ 推送重试队列集成
□ 待办到期自动扫描提醒
□ 启动恢复逻辑（扫 SQLite + 补注册 apscheduler job）
□ systemd 单元：wiki-scheduler.service
□ DevMechin 部署 + 端到端测试
```

## 十一、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|:---:|------|------|
| SQLite 文件损坏 | 低 | 高 | WAL 模式防崩溃；每日 dump；Git 保留 SQL 文本 |
| 企微 API 限频 | 中 | 中 | 推送合并（早报一条）；失败进重试队列 |
| Ollama 意图分类不准 | 中 | 中 | impl 中加确认步骤："您是说要…吗？" |
| 时间解析歧义 | 中 | 低 | LLM 输出 ISO8601；解析失败则追问 |
| Git 长时间不可达 | 低 | 中 | 本地队列积压；恢复后批量推送 |
| DB 迁移失败 | 低 | 高 | 迁移前自动备份当前 .db；失败回滚 |

## 十二、明确不做

- ❌ 不用外部数据库（PostgreSQL/MySQL）—— 杀鸡用牛刀
- ❌ 不做 Web UI —— 企微 Bot + CLI 足够
- ❌ 不做多用户 —— 个人助手，单租户
- ❌ 不用 ORM（SQLAlchemy） —— sqlite3 标准库 + 简单 dataclass 即可
- ❌ 不在 SQLite 存储二进制（图片/PDF）—— 仍走 `raw/assets/` 文件系统
- ❌ 不改造已有模块 —— 纯增量扩展，零破坏性变更

## 十三、关键设计决策

### 决策 1：SQLite 而非纯文件

**选择**：待办/提醒/笔记等高频写入的结构化数据用 SQLite。

**理由**：
- 文件系统做"列出明天到期的所有高优先级待办"需要扫描所有文件并解析 YAML，O(n)；SQLite 用索引 O(log n)
- SQLite 自带 atomic commit，文件系统需要手动实现
- 个人数据量远未到 SQLite 瓶颈
- Python 标准库自带，零新依赖
- SQL dump 为文本文件进入 Git，版本历史可追踪

### 决策 2：SQL dump 作为 Git 备份格式

**选择**：每天 dump SQLite 到 `.sql` 文本文件，Git 版本控制。

**理由**：
- SQL 文本文件 diff 可读（二进制 `.db` 不可 diff）
- `git clone` 即可获取所有数据的历史版本
- 灾难恢复只需 `sqlite3 db < dump.sql`

### 决策 3：文件系统仍是主存储

**选择**：Wiki 知识内容（资料摘要、概念页、综合分析等）维持 Markdown + Git。

**理由**：
- Obsidian 需要 `.md` 文件才能浏览
- 长文本的版本历史在 Git 中更有价值
- 知识内容不需要结构化查询（全文搜索已足够）
- 不破坏现有架构和用户习惯

## 相关

- [[AI 自进化知识系统 — 建设路线图]]
- [[知识库系统全链路架构]]
- [[企业微信Bot—MCP检索与模型交互链路]]
- [[Agent Skills体系]]
- [[Skill 设计模式（Google 5种）]]
- [[Wiki 目录]]
