"""规划引擎 — 意图识别 → 技能匹配 → 执行."""

import importlib.util
import asyncio
import sys
from pathlib import Path
from knowledge_wiki.config import settings
from knowledge_wiki.skill.registry import find_skill, Skill
from knowledge_wiki.skill.engine import match_skill, load_skill_body


def plan(intent: str) -> tuple[Skill | None, str]:
    """分析用户意图，返回匹配的技能和执行计划."""
    skill = match_skill(intent)

    if not skill:
        return None, f"未找到匹配「{intent}」的技能。使用 `skill-list` 查看可用技能。"

    body = load_skill_body(skill) or skill.description

    plan_text = f"## 执行计划：{skill.name}\n\n"
    plan_text += f"**意图**: {intent}\n"
    plan_text += f"**技能**: {skill.name} (v{skill.version})\n"
    plan_text += f"**模型**: {skill.model}\n"
    plan_text += f"**依赖工具**: {', '.join(skill.tools) if skill.tools else '无'}\n"
    plan_text += f"\n{body}"

    return skill, plan_text


def _load_impl(skill: Skill):
    """加载技能的 impl.py 模块，返回 execute 函数或 None."""
    if not skill.path:
        return None

    impl_path = skill.path / "impl.py"
    if not impl_path.exists():
        return None

    module_name = f"knowledge_wiki.skills.{skill.name}"

    # 如果已加载，直接返回
    if module_name in sys.modules:
        mod = sys.modules[module_name]
        return getattr(mod, "execute", None)

    spec = importlib.util.spec_from_file_location(module_name, impl_path)
    if not spec or not spec.loader:
        return None

    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)

    return getattr(mod, "execute", None)


def execute_skill(skill_name: str, context: dict | None = None) -> str:
    """执行指定技能.

    1. 查找技能注册信息
    2. 加载 impl.py 的 execute(context) 函数
    3. 调用 execute 并返回结果
    4. 如无 impl.py，返回 SKILL.md 作为参考

    Args:
        skill_name: 技能名称
        context: 执行上下文，可包含 user_id, input_text, send_md, send_tpl 等

    Returns:
        执行结果文本
    """
    if context is None:
        context = {}

    skill = find_skill(skill_name)
    if not skill:
        return f"技能「{skill_name}」不存在。使用 `skill-list` 查看可用技能。"

    # 尝试加载 impl.py 执行
    execute_fn = _load_impl(skill)
    if execute_fn:
        try:
            if asyncio.iscoroutinefunction(execute_fn):
                result = asyncio.run(execute_fn(context))
            else:
                result = execute_fn(context)
            return result if result else f"技能「{skill.name}」执行完成（无输出）。"
        except Exception as e:
            print(f"[skill] {skill.name} execution failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return f"技能「{skill.name}」执行失败: {e}"

    # Fallback: 返回 SKILL.md 作为参考
    body = load_skill_body(skill)
    if body:
        return f"## {skill.name} (v{skill.version})\n\n{body}\n\n*技能缺少 impl.py，无法自动执行.*"

    return f"技能「{skill.name}」缺少 SKILL.md 定义和 impl.py 实现。"
