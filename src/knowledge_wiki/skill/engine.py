"""渐进式加载引擎 — 三级加载（名称+描述 → SKILL.md 正文 → 脚本/资源）."""

from knowledge_wiki.skill.registry import list_skills, get_skills_for_tier, Skill


def generate_tier1_context() -> str:
    """生成 Tier 1 上下文 —— 所有技能的名称和描述列表，用于 Agent system prompt.

    每个技能仅输出 1-2 行（~50 tokens），20 个技能仅消耗 ~1000 tokens。
    """
    skills = get_skills_for_tier(1)
    if not skills:
        return ""

    lines = ["## 可用技能"]
    for s in skills:
        triggers_str = " | ".join(s.triggers[:3]) if s.triggers else "任意"
        lines.append(f"- `{s.name}` ({triggers_str}): {s.description}")
    return "\n".join(lines)


def load_skill_body(skill: Skill) -> str | None:
    """加载技能完整定义 —— Tier 2，匹配触发条件后加载 SKILL.md 正文."""
    if not skill.path:
        return None

    skill_md = skill.path / "SKILL.md"
    if skill_md.exists():
        return skill_md.read_text()

    # Fallback: construct from skill.json fields
    lines = [f"# {skill.name}", f"\n{skill.description}\n"]
    lines.append(f"- 版本: {skill.version}")
    lines.append(f"- 模型: {skill.model}")
    lines.append(f"- 触发词: {', '.join(skill.triggers)}")
    if skill.tools:
        lines.append(f"- 依赖工具: {', '.join(skill.tools)}")

    return "\n".join(lines)


def load_skill_resources(skill: Skill) -> dict[str, str]:
    """加载技能资源 —— Tier 3，按需加载 scripts/ 和 references/."""
    resources = {}
    if not skill.path:
        return resources

    for subdir in ["scripts", "references"]:
        d = skill.path / subdir
        if d.exists():
            for f in d.iterdir():
                if f.is_file():
                    resources[f"{subdir}/{f.name}"] = f.read_text()

    return resources


def match_skill(intent: str) -> Skill | None:
    """根据用户意图匹配最合适的技能.

    优先级：最长触发词匹配 > 名称包含 > 描述包含.
    长触发词优先（"待办" 长度2 > "喝水" 长度2，相等时取先匹配到的）。
    """
    skills = list_skills()
    intent_lower = intent.lower()

    # 触发词匹配 — 最长优先，同长时 Tier 低者优先（核心技能 > 懒加载）
    best_skill = None
    best_len = 0
    best_tier = 99
    for skill in skills:
        for trigger in skill.triggers:
            if trigger.lower() in intent_lower:
                better = False
                if len(trigger) > best_len:
                    better = True
                elif len(trigger) == best_len and skill.tier < best_tier:
                    better = True
                if better:
                    best_skill = skill
                    best_len = len(trigger)
                    best_tier = skill.tier

    if best_skill:
        return best_skill

    # 名称包含
    for skill in skills:
        if skill.name.lower().replace("-", " ") in intent_lower:
            return skill

    # 描述包含
    for skill in skills:
        if any(word in intent_lower for word in skill.description.lower().split() if len(word) > 2):
            return skill

    return None
