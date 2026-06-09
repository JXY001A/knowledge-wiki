"""技能注册表 — 文件系统即注册表，扫描 skills/ 目录.

设计理念：
    每个技能是 `skills/` 下的一个子目录，目录中包含一个 `skill.json`
    清单文件。注册表通过扫描文件系统动态发现技能，无需手动注册。
    这类似于 VSCode 扩展或 WordPress 插件的发现机制。

三层架构（Tier 体系）：
    Tier 1 — 核心技能，始终加载，提供基础能力（如 wiki 操作）
    Tier 2 — 按需加载，被触发词激活后才注入上下文
    Tier 3 — 懒加载，仅在显式调用时加载，最小化 token 消耗

使用示例：
    >>> from knowledge_wiki.skill.registry import list_skills, find_skill
    >>> skills = list_skills()
    >>> wiki_skill = find_skill("wiki")
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from knowledge_wiki.config import settings


# @dataclass 装饰器：自动生成 __init__、__repr__、__eq__ 三个方法
# 省去手写构造函数的样板代码，直接用类型注解声明字段即可
# 注意：可变默认值（如 list）必须用 field(default_factory=list)，
#       直接写 [] 会导致所有实例共享同一个列表对象
@dataclass
class Skill:
    """技能定义 — skill.json 的内存表示.

    每个 Skill 实例对应 `skills/<name>/skill.json` 的一份解析结果。
    字段含义与 skill.json 中的 key 一一对应。

    Attributes:
        name: 技能唯一标识符，与目录名一致，如 "wiki"、"habit-tracker"
        version: 语义化版本号，用于兼容性检查，默认 "1.0"
        description: 一句话描述技能用途，展示在 skill-list 中
        tier: 加载层级（1=核心常驻, 2=触发加载, 3=显式加载）
        model: 推荐模型，如 "local"（Ollama）或 "deepseek"（DeepSeek API）
        tools: 技能需要调用的 MCP 工具列表，用于权限控制和工具注入
        triggers: 触发词列表，用户消息匹配到任一触发词时激活该技能
        dependencies: 依赖的其他技能名称列表，加载前确保依赖已就绪
        path: 技能目录在文件系统中的绝对路径，运行时注入，不持久化到 JSON
    """
    name: str                          # 技能唯一标识符
    version: str = "1.0"               # 语义化版本号
    description: str = ""              # 一句话描述
    tier: int = 1                      # 加载层级（1/2/3）
    model: str = "local"               # 推荐使用的 LLM 模型
    tools: list[str] = field(default_factory=list)        # 需要的 MCP 工具名列表
    triggers: list[str] = field(default_factory=list)     # 触发词列表
    dependencies: list[str] = field(default_factory=list) # 依赖的其他技能
    path: Path | None = None           # 技能目录的文件系统路径（运行时注入）

    # @classmethod 类方法：第一个参数是类本身(cls)而非实例(self)
    # 工厂方法模式 — 不需要已有实例，直接 Skill.from_json(data) 调用
    # 内部 cls(...) 等价于 Skill(...)，构造并返回新实例
    @classmethod
    def from_json(cls, data: dict, path: Path | None = None) -> "Skill":
        """从 skill.json 的解析结果构造 Skill 实例.

        工厂方法，将 JSON 字典反序列化为 Skill 对象。对缺失字段使用默认值，
        保证向后兼容——新增字段不会导致旧 skill.json 解析失败。

        Args:
            data: json.loads() 解析出的字典，对应 skill.json 的顶层对象
            path: 技能目录的 Path 对象，用于后续定位技能内的脚本/资源文件

        Returns:
            构造完成的 Skill 实例，所有字段已填充默认值

        Example:
            >>> data = {"name": "wiki", "tier": 1, "triggers": ["查询", "wiki"]}
            >>> skill = Skill.from_json(data, path=Path("skills/wiki"))
            >>> skill.name
            'wiki'
        """
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
    """返回 skills/ 注册表根目录的绝对路径.

    路径基于 wiki_root 配置拼接，通常为项目根目录下的 `skills/`。

    Returns:
        Path 对象，指向 skills/ 目录（可能不存在）
    """
    return settings.wiki_root / "agent" / "skills"


def list_skills() -> list[Skill]:
    """扫描 skills/ 目录，列出所有已注册技能.

    遍历 `skills_dir()` 下的每一个子目录，查找其中的 `skill.json` 文件。
    解析成功则构造 Skill 实例加入列表；解析失败则打印警告并跳过，
    不会因为单个技能损坏而阻断整个注册表加载。

    目录按名称排序，保证每次扫描结果顺序一致。

    Returns:
        Skill 列表，按目录名升序排列。若 skills/ 目录不存在则返回空列表。

    Implementation notes:
        - 仅扫描直接子目录，不递归——技能不允许嵌套
        - 跳过不含 skill.json 的子目录（可能是其他用途的目录）
        - JSON 解析异常被捕获并以 [skill] 前缀打印到 stderr
    """
    skills = []
    sd = skills_dir()
    if not sd.exists():
        return skills  # skills/ 目录尚未创建，视为空注册表

    # 按名称排序遍历，确保结果稳定可复现
    for d in sorted(sd.iterdir()):
        if not d.is_dir():
            continue  # 跳过非目录文件（如 README.md）
        json_path = d / "skill.json"
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text())
                skills.append(Skill.from_json(data, path=d))
            except (json.JSONDecodeError, KeyError) as e:
                # 单个技能损坏不影响整体加载，打印警告后继续
                print(f"[skill] invalid {json_path}: {e}", flush=True)

    return skills


def find_skill(name: str) -> Skill | None:
    """按名称查找技能.

    在注册表中线性搜索指定名称的技能。当前实现为 O(n) 线性扫描，
    适合技能数量较少（< 100）的场景。若后续技能数量增长，
    可改为字典索引以优化为 O(1)。

    Args:
        name: 技能名称，与 skill.json 中的 name 字段完全匹配（大小写敏感）

    Returns:
        匹配的 Skill 实例，未找到则返回 None

    Example:
        >>> skill = find_skill("wiki")
        >>> if skill:
        ...     print(f"找到技能: {skill.name} (tier {skill.tier})")
    """
    for skill in list_skills():
        if skill.name == name:
            return skill
    return None


def get_skills_for_tier(tier: int) -> list[Skill]:
    """获取指定加载层级的所有技能.

    按 tier 过滤技能列表，用于分阶段加载：
    - 启动时加载 tier 1（核心技能）
    - 用户输入匹配触发词时加载 tier 2（按需技能）
    - 显式调用时加载 tier 3（懒加载技能）

    Args:
        tier: 加载层级编号（1/2/3）

    Returns:
        属于该 tier 的所有 Skill 实例列表
    """
    return [s for s in list_skills() if s.tier == tier]


def get_skills_summary() -> str:
    """生成所有技能的 Markdown 摘要，供 MCP skill-list 工具返回.

    按 Tier 分组展示技能列表，包含技能名称、版本、描述、触发词和推荐模型。
    输出格式为 Markdown，可直接在 LLM 上下文中使用。

    Tier 分组标签：
        Tier 1 — 核心（始终加载）：基础能力，随系统启动即注入上下文
        Tier 2 — 按需加载：被触发词命中后注入，平衡能力与 token 消耗
        Tier 3 — 懒加载：仅在用户显式调用时加载，最大化节省上下文

    触发词展示截断为前 5 个，避免列表过长影响可读性。

    Returns:
        格式化的 Markdown 字符串。若注册表为空，返回引导信息提示如何创建技能。

    Example output:
        ## 已注册技能（3）

        ### Tier 1: 核心（始终加载）
        - **wiki** (v1.0): 知识库管理
          触发词: 查询, wiki, 知识库 | 模型: local
    """
    skills = list_skills()
    if not skills:
        return (
            "暂无已注册技能。\n\n"
            "在 skills/<name>/skill.json 创建技能定义。\n"
            "参考 skills/SKILL.md 了解格式。"
        )

    lines = [f"## 已注册技能（{len(skills)}）\n"]

    # 按 Tier 1 → 3 分组展示
    for tier in range(1, 4):
        tier_skills = [s for s in skills if s.tier == tier]
        if not tier_skills:
            continue  # 跳过无技能的 tier，保持输出简洁
        # Tier 标签映射，未知 tier 使用默认格式兜底
        tier_label = {
            1: "核心（始终加载）",
            2: "按需加载",
            3: "懒加载",
        }.get(tier, f"Tier {tier}")
        lines.append(f"### Tier {tier}: {tier_label}")
        for s in tier_skills:
            # 截断触发词列表，最多展示前 5 个
            triggers_str = ", ".join(s.triggers[:5]) if s.triggers else "无"
            lines.append(f"- **{s.name}** (v{s.version}): {s.description}")
            lines.append(f"  触发词: {triggers_str} | 模型: {s.model}")
        lines.append("")  # Tier 之间空行分隔

    return "\n".join(lines)
