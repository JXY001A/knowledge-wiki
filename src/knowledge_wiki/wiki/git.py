"""Git 操作 — pull, push, commit, 含失败重试队列."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from knowledge_wiki.config import settings

# 待推送队列文件（本地持久化，git push 失败时写入，定时重试）
PENDING_QUEUE = settings.wiki_root / ".cache" / "git_push_queue.jsonl"


def _run_git(cmd: list[str], timeout: int = 60) -> str:
    """执行 git 命令，返回 stdout+stderr."""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            cwd=settings.wiki_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (result.stdout + result.stderr).strip()
    except Exception as e:
        return f"git error: {e}"


def pull() -> str:
    """从 GitHub 拉取最新变更."""
    return _run_git(["pull", "--rebase", "origin", "main"])


def push(commit_msg: str) -> str:
    """暂存所有变更、提交并推送。失败时写本地队列."""
    _run_git(["add", "-A"])

    # 检查是否有变更
    diff = _run_git(["diff", "--staged", "--quiet"])
    commit_result = _run_git(["commit", "-m", commit_msg])
    if "nothing to commit" in commit_result:
        return "nothing to commit"

    # 推送
    push_result = _run_git(["push", "origin", "main"])
    if "error" in push_result.lower() or "fatal" in push_result.lower():
        # 推送失败：commit 已成功但 push 失败，写入待推送队列
        _enqueue_pending(commit_msg, push_result)
        return f"COMMITTED (push queued): {push_result[:200]}"

    # 推送成功，同时尝试清空待推送队列
    _flush_pending_queue()
    return push_result


def commit_and_push(msg: str) -> None:
    """便捷方法：add → commit → push。失败写日志 + 队列，不抛异常."""
    try:
        result = push(msg)
        if "nothing to commit" not in result:
            print(f"[git] pushed: {msg}", flush=True)
    except Exception as e:
        # 不再静默吞：写日志 + 入队
        error_msg = f"[git] PUSH FAILED: {e}"
        print(error_msg, flush=True)
        _enqueue_pending(msg, str(e))


def retry_pending_pushes() -> str:
    """重试待推送队列中的所有 commit。返回重试结果摘要.

    Returns:
        重试结果描述
    """
    if not PENDING_QUEUE.exists():
        return "no pending pushes"

    entries = []
    with open(PENDING_QUEUE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not entries:
        PENDING_QUEUE.unlink(missing_ok=True)
        return "no pending pushes"

    # 尝试一次 push
    result = _run_git(["push", "origin", "main"])
    if "error" not in result.lower() and "fatal" not in result.lower():
        # 成功：清空队列
        PENDING_QUEUE.unlink(missing_ok=True)
        return f"flushed {len(entries)} pending pushes"

    return f"retry failed: {len(entries)} pending. {result[:200]}"


def pending_count() -> int:
    """返回待推送条目数."""
    if not PENDING_QUEUE.exists():
        return 0
    try:
        with open(PENDING_QUEUE) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _enqueue_pending(msg: str, error: str) -> None:
    """追加一条待推送记录到本地队列."""
    PENDING_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "msg": msg[:200],
        "error": error[:200],
        "time": datetime.now().isoformat(),
    }
    with open(PENDING_QUEUE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _flush_pending_queue() -> None:
    """推送成功后自动重试清空队列."""
    if PENDING_QUEUE.exists():
        retry_pending_pushes()
