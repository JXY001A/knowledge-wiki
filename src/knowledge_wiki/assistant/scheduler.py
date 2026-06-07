"""个人助手调度器 — APScheduler + JSON 持久化.

系统预置 Job：
    - 早报推送：每天 08:00
    - 晚报推送：每天 21:00
    - SQL dump 备份：每天 02:17
    - 文件快照：每天 03:13
    - Git 推送重试：每 5 分钟
    - 待办到期扫描：每小时

Job 持久化：JSON 文件（wiki/.data/scheduler_jobs.json），启动时加载，停止时保存。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from knowledge_wiki.config import settings

_log = logging.getLogger(__name__)

# Job 持久化文件
JOBS_FILE = settings.wiki_root / "wiki" / ".data" / "scheduler_jobs.json"

# 单例
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """获取调度器单例（懒初始化）."""
    global _scheduler
    if _scheduler is None:
        _scheduler = _create_scheduler()
    return _scheduler


def _create_scheduler() -> BackgroundScheduler:
    """创建调度器，注册系统预置 Job，恢复持久化 Job."""
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # ---- 系统预置 Job ----

    # 早报
    scheduler.add_job(
        _job_morning_brief,
        CronTrigger(hour=8, minute=7),
        id="system:morning-brief",
        name="早报推送",
        replace_existing=True,
    )

    # 晚报
    scheduler.add_job(
        _job_evening_brief,
        CronTrigger(hour=21, minute=7),
        id="system:evening-brief",
        name="晚报推送",
        replace_existing=True,
    )

    # SQL dump 备份
    scheduler.add_job(
        _job_db_backup,
        CronTrigger(hour=2, minute=17),
        id="system:db-backup",
        name="数据库备份",
        replace_existing=True,
    )

    # 文件快照
    scheduler.add_job(
        _job_file_snapshot,
        CronTrigger(hour=3, minute=13),
        id="system:file-snapshot",
        name="文件快照",
        replace_existing=True,
    )

    # Git 推送重试
    scheduler.add_job(
        _job_git_retry,
        CronTrigger(minute="*/5"),
        id="system:git-retry",
        name="Git 推送重试",
        replace_existing=True,
    )

    # 待办到期扫描
    scheduler.add_job(
        _job_deadline_scan,
        CronTrigger(minute=7),
        id="system:deadline-scan",
        name="待办到期扫描",
        replace_existing=True,
    )

    # 恢复持久化 Job
    _restore_jobs(scheduler)

    return scheduler


def start_scheduler() -> None:
    """启动调度器."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        _log.info("调度器已启动，%d 个 job", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """停止调度器并持久化."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _save_jobs(_scheduler)
        _scheduler.shutdown(wait=False)
        _log.info("调度器已停止")
        _scheduler = None


def add_reminder_job(reminder_id: str, content: str, trigger_at: str) -> None:
    """动态添加提醒 Job.

    Args:
        reminder_id: 提醒记录 ID
        content: 提醒内容
        trigger_at: 触发时间 ISO8601
    """
    scheduler = get_scheduler()
    scheduler.add_job(
        _job_fire_reminder,
        DateTrigger(run_date=trigger_at, timezone="Asia/Shanghai"),
        id=f"remind:{reminder_id}",
        name=content[:60],
        kwargs={"reminder_id": reminder_id, "content": content},
        replace_existing=True,
    )
    _save_jobs(scheduler)


def remove_reminder_job(reminder_id: str) -> None:
    """移除提醒 Job."""
    scheduler = get_scheduler()
    job_id = f"remind:{reminder_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        _save_jobs(scheduler)


# ---- 系统 Job 实现（占位，后续 Phase 实现）----

def _job_morning_brief():
    """早报推送."""
    _log.info("[scheduler] 早报时间")


def _job_evening_brief():
    """晚报推送."""
    _log.info("[scheduler] 晚报时间")


def _job_db_backup():
    """数据库备份."""
    try:
        from knowledge_wiki.assistant.backup import backup_database
        result = backup_database()
        _log.info("[scheduler] 数据库备份: %s", result)
    except Exception as e:
        _log.warning("[scheduler] 备份失败: %s", e)


def _job_file_snapshot():
    """文件快照."""
    try:
        from knowledge_wiki.assistant.backup import snapshot_files
        result = snapshot_files()
        _log.info("[scheduler] 文件快照: %s", result)
    except Exception as e:
        _log.warning("[scheduler] 快照失败: %s", e)


def _job_git_retry():
    """Git 推送重试."""
    try:
        from knowledge_wiki.wiki.git import retry_pending_pushes, pending_count
        count = pending_count()
        if count > 0:
            result = retry_pending_pushes()
            _log.info("[scheduler] git 重试: %d 条, %s", count, result)
    except Exception as e:
        _log.warning("[scheduler] git 重试失败: %s", e)


def _job_deadline_scan():
    """待办到期扫描."""
    try:
        from knowledge_wiki.assistant.db import get_db
        from datetime import datetime, timedelta
        conn = get_db()
        soon = (datetime.now() + timedelta(hours=1)).isoformat()
        now = datetime.now().isoformat()
        rows = conn.execute(
            "SELECT COUNT(*) FROM todos WHERE status='pending' AND deadline BETWEEN ? AND ?",
            [now, soon],
        ).fetchone()
        if rows and rows[0] > 0:
            _log.info("[scheduler] %d 个待办即将到期", rows[0])
        conn.close()
    except Exception as e:
        _log.warning("[scheduler] 待办扫描失败: %s", e)


def _job_fire_reminder(reminder_id: str, content: str):
    """触发提醒（后续 Phase 接入企微推送）."""
    _log.info("[scheduler] 提醒触发: %s - %s", reminder_id, content)


# ---- 持久化 ----

def _save_jobs(scheduler: BackgroundScheduler) -> None:
    """保存所有动态 Job 到 JSON 文件（系统预置 Job 不保存）."""
    try:
        JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        jobs_data = []
        for job in scheduler.get_jobs():
            # 只保存 remind:* 动态 job，系统预置 job 不保存
            if job.id.startswith("remind:"):
                jobs_data.append({
                    "id": job.id,
                    "name": job.name,
                    "trigger": str(job.trigger),
                    "next_run": str(job.next_run_time) if hasattr(job, 'next_run_time') and job.next_run_time else None,
                    "kwargs": dict(job.kwargs),
                })

        JOBS_FILE.write_text(json.dumps(jobs_data, ensure_ascii=False, indent=2))
    except Exception as e:
        _log.warning("保存 jobs 失败: %s", e)


def _restore_jobs(scheduler: BackgroundScheduler) -> None:
    """从 JSON 文件恢复动态 Job."""
    if not JOBS_FILE.exists():
        return

    try:
        jobs_data = json.loads(JOBS_FILE.read_text())
        restored = 0
        for jd in jobs_data:
            job_id = jd.get("id", "")
            if not job_id.startswith("remind:"):
                continue

            kwargs = jd.get("kwargs", {})
            trigger_at = kwargs.get("trigger_at") or jd.get("next_run")
            if not trigger_at:
                continue

            # 跳过已过期
            from datetime import datetime, timezone
            try:
                run_time = datetime.fromisoformat(trigger_at)
                if run_time < datetime.now(timezone.utc):
                    continue
            except (ValueError, TypeError):
                continue

            scheduler.add_job(
                _job_fire_reminder,
                DateTrigger(run_date=trigger_at, timezone="Asia/Shanghai"),
                id=job_id,
                name=jd.get("name", ""),
                kwargs=kwargs,
                replace_existing=True,
            )
            restored += 1

        if restored > 0:
            _log.info("恢复 %d 个提醒 job", restored)
    except Exception as e:
        _log.warning("恢复 jobs 失败: %s", e)
