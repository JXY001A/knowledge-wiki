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
    scheduler = BackgroundScheduler(
        timezone="Asia/Shanghai",
        job_defaults={"misfire_grace_time": 3600},  # 1小时内错过的 job 仍触发
    )

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

    # 每周自检报告（周日 10:00）
    scheduler.add_job(
        _job_weekly_report,
        CronTrigger(day_of_week="sun", hour=10, minute=7),
        id="system:weekly-report",
        name="每周自检报告",
        replace_existing=True,
    )

    # 每分钟同步数据库提醒到 scheduler（webhook 独立进程无法直接注册 job）
    scheduler.add_job(
        _job_sync_reminders,
        CronTrigger(minute="*"),
        id="system:sync-reminders",
        name="同步数据库提醒",
        replace_existing=True,
    )

    # 恢复持久化 Job + 扫描数据库补注册
    _restore_jobs(scheduler)
    _recover_from_db(scheduler)

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


def add_reminder_job(reminder_id: str, content: str, trigger_at: str, user_id: str = "") -> None:
    """动态添加提醒 Job.

    Args:
        reminder_id: 提醒记录 ID
        content: 提醒内容
        trigger_at: 触发时间 ISO8601
        user_id: 企微 UserID（用于主动推送）
    """
    scheduler = get_scheduler()
    scheduler.add_job(
        _job_fire_reminder,
        DateTrigger(run_date=trigger_at, timezone="Asia/Shanghai"),
        id=f"remind:{reminder_id}",
        name=content[:60],
        kwargs={"reminder_id": reminder_id, "content": content, "user_id": user_id},
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
    """早报推送（通过企微主动推送）."""
    _push_to_user("system", "☀️ 早上好！新的一天开始了。\n\n发送「早报」查看今日日程。")


def _job_evening_brief():
    """晚报推送（通过企微主动推送）."""
    _push_to_user("system", "🌙 晚上好！发送「晚报」查看今日回顾。")


def _push_to_user(user_id: str, content: str) -> bool:
    """通过企微 API 主动推送消息给用户.

    Args:
        user_id: 企微 UserID（'system' 表示推送给最近活跃用户）
        content: markdown 消息内容

    Returns:
        是否推送成功
    """
    try:
        from knowledge_wiki.webhook.wechat.api import send_markdown

        # 如果 user_id 为 'system' 或空，尝试从最近提醒获知真实用户
        actual_user = user_id
        if not actual_user or actual_user == "system":
            actual_user = _get_last_active_user()

        if not actual_user or actual_user == "system":
            _log.info("[scheduler] 无活跃用户，跳过推送")
            return False

        ok = send_markdown(actual_user, content)
        if ok:
            _log.info("[scheduler] 推送成功: %s → %s", actual_user, content[:50])
        else:
            _log.warning("[scheduler] 推送失败: %s", actual_user)
        return ok
    except Exception as e:
        _log.warning("[scheduler] 推送异常: %s", e)
        return False


def _get_last_active_user() -> str:
    """从 reminders 表获取最近设置提醒的 user_id."""
    try:
        from knowledge_wiki.assistant.db import get_db, init_schema
        conn = get_db()
        init_schema(conn)
        row = conn.execute(
            "SELECT user_id FROM reminders WHERE user_id != '' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row["user_id"] if row else ""
    except Exception:
        return ""


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


def _job_weekly_report():
    """生成并推送周度自检报告."""
    try:
        from knowledge_wiki.evolve.reporter import weekly_report
        report = weekly_report()
        _push_to_user("system", report[:3000])
    except Exception as e:
        _log.warning("[scheduler] 周报生成失败: %s", e)


def _job_sync_reminders():
    """每分钟从数据库同步新提醒到 scheduler."""
    try:
        from knowledge_wiki.assistant.db import get_db, init_schema
        from knowledge_wiki.assistant.models import Reminder
        from datetime import datetime, timezone

        conn = get_db()
        init_schema(conn)
        rows = conn.execute(
            "SELECT * FROM reminders WHERE status='active' AND trigger_at > ?",
            [datetime.now(timezone.utc).isoformat()],
        ).fetchall()
        conn.close()

        added = 0
        for r in rows:
            rem = Reminder.from_row(r)
            job_id = f"remind:{rem.id}"
            if get_scheduler().get_job(job_id):
                continue
            try:
                get_scheduler().add_job(
                    _job_fire_reminder,
                    DateTrigger(run_date=rem.trigger_at, timezone="Asia/Shanghai"),
                    id=job_id,
                    name=rem.content[:60],
                    kwargs={"reminder_id": rem.id, "content": rem.content, "user_id": rem.user_id},
                    replace_existing=True,
                )
                added += 1
            except Exception as e:
                _log.warning("sync 提醒 %s 失败: %s", rem.id, e)

        if added > 0:
            _log.info("同步 %d 个新提醒", added)
    except Exception as e:
        _log.warning("sync 提醒失败: %s", e)


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


def _job_fire_reminder(reminder_id: str, content: str, user_id: str = ""):
    """触发提醒并推送企微消息."""
    _log.info("[scheduler] 提醒触发: %s - %s (user=%s)", reminder_id, content, user_id)

    # 推送企微消息
    msg = f"⏰ **提醒**\n\n{content}"
    ok = _push_to_user(user_id, msg)

    # 标记提醒已触发
    if ok or not user_id:
        try:
            from datetime import datetime
            from knowledge_wiki.assistant.db import get_db, init_schema
            conn = get_db()
            init_schema(conn)
            conn.execute(
                "UPDATE reminders SET status='fired', fired_at=? WHERE id=?",
                [datetime.now().isoformat(), reminder_id],
            )
            conn.commit()
            conn.close()
        except Exception:
            pass


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


def _recover_from_db(scheduler: BackgroundScheduler) -> None:
    """启动时从数据库恢复所有活跃提醒（JSON 文件丢失时的保障）."""
    try:
        from knowledge_wiki.assistant.db import get_db, init_schema
        from knowledge_wiki.assistant.models import Reminder
        from datetime import datetime, timezone

        conn = get_db()
        init_schema(conn)
        rows = conn.execute(
            "SELECT * FROM reminders WHERE status='active' AND trigger_at > ?",
            [datetime.now(timezone.utc).isoformat()],
        ).fetchall()
        conn.close()

        restored = 0
        for r in rows:
            rem = Reminder.from_row(r)
            job_id = f"remind:{rem.id}"
            if scheduler.get_job(job_id):
                continue  # 已存在

            try:
                scheduler.add_job(
                    _job_fire_reminder,
                    DateTrigger(run_date=rem.trigger_at, timezone="Asia/Shanghai"),
                    id=job_id,
                    name=rem.content[:60],
                    kwargs={"reminder_id": rem.id, "content": rem.content, "user_id": rem.user_id},
                    replace_existing=True,
                )
                restored += 1
            except Exception as e:
                _log.warning("恢复提醒 %s 失败: %s", rem.id, e)

        if restored > 0:
            _log.info("从数据库恢复 %d 个提醒", restored)
    except Exception as e:
        _log.warning("从数据库恢复失败: %s", e)


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
