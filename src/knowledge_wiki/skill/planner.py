"""规划引擎 — 意图识别 → 技能路由."""

from knowledge_wiki.skill.registry import find_skill, Skill
from knowledge_wiki.skill.engine import match_skill, load_skill_body


def plan(intent: str) -> tuple[Skill | None, str]:
    """分析用户意图，返回匹配的技能和执行计划.

    Returns:
        (matched_skill, execution_plan): 技能对象和人类可读的执行计划
    """
    skill = match_skill(intent)

    if not skill:
        return None, f"未找到匹配「{intent}」的技能。\n使用 `skill-list` 查看可用技能。"

    # 加载技能完整定义
    body = load_skill_body(skill) or skill.description

    plan_text = f"## 执行计划：{skill.name}\n\n"
    plan_text += f"**意图**: {intent}\n"
    plan_text += f"**技能**: {skill.name} (v{skill.version})\n"
    plan_text += f"**模型**: {skill.model}\n"
    plan_text += f"**依赖工具**: {', '.join(skill.tools) if skill.tools else '无'}\n"
    plan_text += f"\n{body}"

    return skill, plan_text


def execute_skill(skill_name: str, intent: str) -> str:
    """执行指定技能（通过 MCP 暴露为 skill-execute）.

    当前为骨架实现，Phase 2 完整实现时需要：
    1. 加载技能 SKILL.md + impl.py
    2. 根据 skill.json 的 model 字段选择 LLM
    3. 按步骤执行
    4. 返回结果
    """
    skill = find_skill(skill_name)
    if not skill:
        return f"技能「{skill_name}」不存在。使用 `skill-list` 查看可用技能。"

    body = load_skill_body(skill)
    if not body:
        return f"技能「{skill_name}」缺少 SKILL.md 定义。"

    return f"## 执行技能：{skill.name}\n\n{body}\n\n---\n*Phase 2 骨架：完整执行引擎待实现.*"
