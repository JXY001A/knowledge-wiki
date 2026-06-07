"""渐进式加载引擎 — 三级加载（名称+描述 → SKILL.md 正文 → 脚本/资源）."""

import json
import urllib.request
from knowledge_wiki.skill.registry import list_skills, get_skills_for_tier, Skill
from knowledge_wiki.config import settings


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

    # 触发词匹配 — 最长优先 > 同长时靠前优先 > 同位置时低 Tier 优先
    best_skill = None
    best_len = 0
    best_pos = 9999
    best_tier = 99
    for skill in skills:
        for trigger in skill.triggers:
            pos = intent_lower.find(trigger.lower())
            if pos >= 0:
                better = False
                if len(trigger) > best_len:
                    better = True
                elif len(trigger) == best_len:
                    if pos < best_pos:
                        better = True
                    elif pos == best_pos and skill.tier < best_tier:
                        better = True
                if better:
                    best_skill = skill
                    best_len = len(trigger)
                    best_pos = pos
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


def classify_intent_llm(text: str) -> str | None:
    """用本地 Ollama 做意图分类，返回技能名.

    比关键词匹配强在：理解语义而非匹配字符串。
    """
    skills = list_skills()
    if not skills:
        return None

    skill_list = "\n".join(
        f"- {s.name}: {s.description}"
        for s in sorted(skills, key=lambda s: s.tier)
    )

    prompt = f"""你是意图分类器。根据用户输入，从以下技能中选择最匹配的一个。

可用技能：
{skill_list}

规则：
- 用户说"待办/todo/任务/要做/添加" → todo-manage
- 用户说"提醒/闹钟/几点/叫我/记得" → remind-set
- 用户说"笔记/备忘/记一下" → note-quick
- 用户说"书签/收藏/稍后读" → bookmark-save
- 用户说"今天/明天/日程/安排" → schedule-view
- 用户说"日报/早报/晚报/简报/总结" → daily-brief
- 用户说"打卡/习惯" → habit-track
- 用户问问题（以?开头或包含"是什么/怎么/为什么"） → query-knowledge
- URL链接 → ingest-article
- 其他无明确意图的文本 → save-note

只输出技能名称，不要解释。"""

    try:
        body = json.dumps({
            "model": "qwen2.5:3b",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "options": {"num_predict": 20, "temperature": 0.0},
        }).encode()

        req = urllib.request.Request(
            f"{settings.ollama_base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            skill_name = result.get("message", {}).get("content", "").strip().lower()

        valid_names = {s.name for s in skills}
        for name in valid_names:
            if name in skill_name:
                return name

        return None
    except Exception:
        return None


def classify_todo_action(text: str) -> dict:
    """用 LLM 解析待办操作：创建/完成/删除/列表，提取结构化字段."""
    import re

    prompt = """你是待办解析器。分析用户输入，输出 JSON。

格式：{"action":"create|complete|delete|list","title":"标题(≤20字)","priority":"high|medium|low","deadline":"YYYY-MM-DD或null","tags":["标签"]}

规则：
- action: "完成/做了/搞定/done"→complete, "取消/删除"→delete, "列出/查看/有哪些/list"→list, 其他→create
- title: 核心待办事项，去掉时间/优先级/标签修饰词
- priority: "紧急/重要/高优先/high"→high, "不急/低优先/low"→low, 默认→medium
- deadline: 今天=2026-06-07, 明天=2026-06-08, 后天=2026-06-09, 下周一=下周一日期
- tags: 从 #标签 或关键词提取

只输出JSON。"""

    try:
        body = json.dumps({
            "model": "qwen2.5:3b",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "options": {"num_predict": 200, "temperature": 0.0},
        }).encode()

        req = urllib.request.Request(
            f"{settings.ollama_base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            raw = result.get("message", {}).get("content", "").strip()

        m = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        return {"action": "create", "title": text[:40], "priority": "medium", "deadline": None, "tags": []}
    except Exception:
        return {"action": "create", "title": text[:40], "priority": "medium", "deadline": None, "tags": []}
