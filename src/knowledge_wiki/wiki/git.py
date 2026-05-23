"""Git 操作 — pull, push, commit."""

import subprocess
from pathlib import Path
from knowledge_wiki.config import settings


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
    """暂存所有变更、提交并推送."""
    _run_git(["add", "-A"])
    diff = _run_git(["diff", "--staged", "--quiet"])
    result = _run_git(["commit", "-m", commit_msg])
    if "nothing to commit" in result:
        return "nothing to commit"
    return _run_git(["push", "origin", "main"])


def commit_and_push(msg: str) -> None:
    """便捷方法：add → commit → push，静默失败."""
    try:
        push(msg)
    except Exception:
        pass
