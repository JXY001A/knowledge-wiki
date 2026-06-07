"""数据备份 — SQL dump + 文件快照.

备份策略：
    SQL dump：每天调用 sqlite3 .dump → SQL 文本 → raw/assets/db-backup/（进 Git）
    文件快照：每天 tar czf wiki/ + raw/ → .cache/backups/（不入 Git，保留 7 天）
"""

import logging
import subprocess
import tarfile
from datetime import datetime, timedelta
from pathlib import Path
from knowledge_wiki.config import settings

_log = logging.getLogger(__name__)

WIKI_ROOT = settings.wiki_root
BACKUP_DIR = WIKI_ROOT / ".cache" / "backups"
DB_DUMP_DIR = WIKI_ROOT / "raw" / "assets" / "db-backup"

# 数据库文件（相对于 WIKI_ROOT）
DB_FILES = [
    "wiki/.data/assistant.db",
    "wiki/.data/memory.db",
]

# 快照保留天数
SNAPSHOT_RETENTION_DAYS = 7


def backup_database() -> str:
    """SQL dump 备份：将 SQLite 数据库 dump 为 SQL 文本文件.

    SQL 文本文件进入 Git 版本控制，可通过 git log 追踪数据变化。
    二进制 .db 文件不入 Git（已被 .gitignore 排除）。

    Returns:
        备份结果描述
    """
    DB_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    backed_up = []

    for db_rel in DB_FILES:
        db_path = WIKI_ROOT / db_rel
        if not db_path.exists():
            continue

        dump_file = DB_DUMP_DIR / f"{Path(db_rel).stem}-{today}.sql"
        try:
            result = subprocess.run(
                ["sqlite3", str(db_path), ".dump"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                dump_file.write_text(result.stdout, encoding="utf-8")
                backed_up.append(dump_file.name)

                # 清理旧 dump（保留最近 7 天）
                _cleanup_old_dumps(Path(db_rel).stem, keep=7)
            else:
                _log.warning("dump %s 失败: %s", db_rel, result.stderr[:200])
        except Exception as e:
            _log.warning("dump %s 异常: %s", db_rel, e)

    if backed_up:
        return f"已备份 {len(backed_up)} 个数据库: {', '.join(backed_up)}"

    # 如果没有数据库文件存在，尝试创建空 dump 避免 git 报错
    if not any((WIKI_ROOT / db_rel).exists() for db_rel in DB_FILES):
        return "无数据库文件需备份"

    return "备份完成"


def _cleanup_old_dumps(db_stem: str, keep: int = 7) -> None:
    """清理超过 keep 天的旧 SQL dump 文件."""
    if not DB_DUMP_DIR.exists():
        return

    cutoff = datetime.now() - timedelta(days=keep)
    for f in DB_DUMP_DIR.glob(f"{db_stem}-*.sql"):
        try:
            # 从文件名提取日期
            name = f.stem  # e.g., "assistant-20260607"
            date_str = name.split("-")[-1]
            file_date = datetime.strptime(date_str, "%Y%m%d")
            if file_date < cutoff:
                f.unlink()
        except (ValueError, IndexError):
            pass


def snapshot_files() -> str:
    """文件快照：压缩 wiki/ + raw/ 目录.

    保留最近 7 天的快照，旧的自动删除。
    存放在 .cache/backups/（不入 Git）。

    Returns:
        快照结果描述
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    archive_name = BACKUP_DIR / f"wiki-snapshot-{today}.tar.gz"

    # 如果今天已经快照过，跳过
    if archive_name.exists():
        return f"今日快照已存在: {archive_name.name}"

    try:
        with tarfile.open(archive_name, "w:gz") as tar:
            # 备份 wiki/
            wiki_dir = WIKI_ROOT / "wiki"
            if wiki_dir.exists():
                tar.add(wiki_dir, arcname="wiki")
            # 备份 raw/
            raw_dir = WIKI_ROOT / "raw"
            if raw_dir.exists():
                tar.add(raw_dir, arcname="raw")

        size_mb = archive_name.stat().st_size / (1024 * 1024)

        # 清理旧快照
        _cleanup_old_snapshots()

        return f"快照已创建: {archive_name.name} ({size_mb:.1f} MB)"
    except Exception as e:
        _log.warning("快照失败: %s", e)
        return f"快照失败: {e}"


def _cleanup_old_snapshots() -> None:
    """清理超过 SNAPSHOT_RETENTION_DAYS 天的快照."""
    if not BACKUP_DIR.exists():
        return

    cutoff = datetime.now() - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    for f in BACKUP_DIR.glob("wiki-snapshot-*.tar.gz"):
        try:
            # 文件修改时间
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                _log.info("清理旧快照: %s", f.name)
        except Exception:
            pass
