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


# 强信号词 → 技能映射（预处理，不需要 LLM）
# 这些词足够明确，即使 LLM 误判也能纠正
_STRONG_SIGNALS = [
    (["加到待办", "加入到待办", "添加到待办", "记一个待办", "创建待办", "新建待办", "加一个待办", "弄到待办"], "todo-manage"),
    (["待办列表", "查看待办", "我的待办", "有哪些待办", "列出待办"], "todo-manage"),
    (["记一下", "记个笔记", "备忘", "闪念"], "note-quick"),
    (["收藏链接", "收藏网址", "加个书签"], "bookmark-save"),
    (["今天要做什么", "今天有什么", "明天要做什么", "我的日程"], "schedule-view"),
    (["早报", "晚报", "今日简报"], "daily-brief"),
    (["打卡", "习惯打卡"], "habit-track"),
    (["健康检查", "巡检", "知识库检查"], "lint-wiki"),
]


def _check_strong_signals(text: str) -> str | None:
    """检查文本是否包含强信号词，直接返回技能名."""
    for keywords, skill_name in _STRONG_SIGNALS:
        for kw in keywords:
            if kw in text:
                return skill_name
    return None


def classify_intent_llm(text: str) -> str | None:
    """用本地 Ollama 做意图分类，返回技能名.

    先检查强信号词（不需要 LLM），未命中时再用 LLM 分类。
    """
    # 1. 强信号词检查
    result = _check_strong_signals(text)
    if result:
        return result

    skills = list_skills()
    if not skills:
        return None

    skill_list = "\n".join(
        f"- {s.name}: {s.description}"
        for s in sorted(skills, key=lambda s: s.tier)
    )

    prompt = f"""你是意图分类器。仔细分析用户输入的真实意图，选择最匹配的技能。

可用技能：
{skill_list}

规则：
1. 用户说"待办/加到待办/加入到待办/todo" → todo-manage
2. 用户描述一项任务/活动（如"提醒我上班""提醒我喝水""提醒我开会"）→ todo-manage
3. 纯时间提醒（如"3点叫我""设个闹钟""到时间提醒我"）→ remind-set
4. 用户说"笔记/备忘/记一下" → note-quick
5. 用户说"书签/收藏/稍后读" → bookmark-save
6. 用户问"今天/明天要做什么" → schedule-view
7. 用户说"日报/早报/晚报" → daily-brief
8. 用户说"打卡/习惯" → habit-track
9. 用户问问题 → query-knowledge
10. URL链接 → ingest-article

关键区别：todo-manage管任务（提醒我上班/喝水/开会），remind-set管时间通知（3点叫我/设闹钟）。

只输出技能名称。"""

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
    from datetime import datetime, timedelta

    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    prompt = f"""分析用户输入，输出JSON。今天={today}，明天={tomorrow}。

规则：
1. action: 含"完成/做了/搞定"→"complete", "取消/删除"→"delete", "列出/查看/有哪些"→"list", 其他→"create"
2. title: 核心待办标题(≤20字)，去掉时间/优先级/标签等修饰词
3. priority: 含"紧急/重要/高优先"→"high", "不急/低优先"→"low", 默认→"medium"
4. deadline: 今天={today}, 明天={tomorrow}, 无明确日期→null
5. tags: 从#标签提取的数组，无→[]

示例:
输入:"提交Q2报告 高优先级 明天"→{{"action":"create","title":"提交Q2报告","priority":"high","deadline":"{tomorrow}","tags":[]}}
输入:"代码review做完了"→{{"action":"complete","title":"代码review","priority":"medium","deadline":null,"tags":[]}}
输入:"待办列表"→{{"action":"list","title":"","priority":"medium","deadline":null,"tags":[]}}

只输出JSON:"""

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
