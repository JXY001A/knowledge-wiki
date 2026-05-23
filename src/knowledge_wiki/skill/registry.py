"""技能注册表 — 文件系统即注册表，扫描 skills/ 目录."""

import json
from pathlib import Path
from dataclasses import dataclass, field
from knowledge_wiki.config import settings


@dataclass
class Skill:
    """技能定义."""
    name: str
    version: str = "1.0"
    description: str = ""
    tier: int = 1
    model: str = "local"
    tools: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    path: Path | None = None

    @classmethod
    def from_json(cls, data: dict, path: Path | None = None) -> "Skill":
        """从 skill.json 创建 Skill 实例."""
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            tier=data.get("tier", 1),
            model=data.get("model", "local"),
            tools=data.get("tools", []),
            triggers=data.get("triggers", []),
            dependencies=data.get("dependencies", []),
            path=path,
        )


def skills_dir() -> Path:
    """返回 skills/ 注册表根目录."""
    return settings.wiki_root / "skills"


def list_skills() -> list[Skill]:
    """列出所有已注册技能."""
    skills = []
    sd = skills_dir()
    if not sd.exists():
        return skills

    for d in sorted(sd.iterdir()):
        if not d.is_dir():
            continue
        json_path = d / "skill.json"
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text())
                skills.append(Skill.from_json(data, path=d))
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[skill] invalid {json_path}: {e}", flush=True)

    return skills


def find_skill(name: str) -> Skill | None:
    """按名称查找技能."""
    for skill in list_skills():
        if skill.name == name:
            return skill
    return None


def get_skills_for_tier(tier: int) -> list[Skill]:
    """获取指定 tier 的所有技能."""
    return [s for s in list_skills() if s.tier == tier]


def get_skills_summary() -> str:
    """获取所有技能的摘要列表（用于 MCP skill-list）."""
    skills = list_skills()
    if not skills:
        return "暂无已注册技能。\n\n在 skills/<name>/skill.json 创建技能定义。\n参考 skills/SKILL.md 了解格式。"

    lines = [f"## 已注册技能（{len(skills)}）\n"]

    for tier in range(1, 4):
        tier_skills = [s for s in skills if s.tier == tier]
        if not tier_skills:
            continue
        tier_label = {1: "核心（始终加载）", 2: "按需加载", 3: "懒加载"}.get(tier, f"Tier {tier}")
        lines.append(f"### Tier {tier}: {tier_label}")
        for s in tier_skills:
            triggers_str = ", ".join(s.triggers[:5]) if s.triggers else "无"
            lines.append(f"- **{s.name}** (v{s.version}): {s.description}")
            lines.append(f"  触发词: {triggers_str} | 模型: {s.model}")
        lines.append("")

    return "\n".join(lines)
