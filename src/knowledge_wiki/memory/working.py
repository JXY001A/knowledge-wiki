"""工作记忆 — 会话上下文提取、压缩与注入.

提供：
    1. extract_context() — 从记忆库中提取最近操作作为上下文
    2. compress_context() — Token 预算内的上下文压缩
    3. build_system_prompt_suffix() — 生成可注入 System Prompt 的记忆片段
"""

import re
from knowledge_wiki.memory.reader import recent_events
from knowledge_wiki.memory.models import EpisodicRecord

# Token 预算 — 上下文注入不要超过此值（留给主内容足够空间）
WORKING_MEMORY_TOKEN_BUDGET = 500  # ~250 中文字


def extract_context(
    limit: int = 5,
    event_types: list[str] | None = None,
    user_id: str | None = None,
) -> list[EpisodicRecord]:
    """从记忆库中提取最近操作上下文.

    Args:
        limit: 返回最近 N 条
        event_types: 可选筛选类型
        user_id: 可选筛选用户

    Returns:
        EpisodicRecord 列表（时间降序）
    """
    events = recent_events(limit=limit, user_id=user_id)

    if event_types:
        events = [e for e in events if e.event_type in event_types]

    return events[:limit]


def compress_context(events: list[EpisodicRecord], max_tokens: int = WORKING_MEMORY_TOKEN_BUDGET) -> str:
    """将事件列表压缩为 Token 预算内的上下文文本.

    压缩策略：
        1. 先尝试完整摘要（1 行/事件）
        2. 若超预算，合并相近主题的事件
        3. 若仍超，只保留标题

    Args:
        events: 事件列表
        max_tokens: 最大 token 预算

    Returns:
        markdown 格式的上下文
    """
    if not events:
        return ""

    # 粗估 token 数：中文 1 字符 ≈ 1 token，英文 1 词 ≈ 1 token
    def _count(text: str) -> int:
        cn = len(re.findall(r"[一-鿿]", text))
        en = len(re.findall(r"[a-zA-Z]+", text))
        return cn + en + len(text) // 4  # 其余字符折半

    # 策略 1：一行摘要
    lines = ["## 上下文记忆", ""]
    icons = {"query": "🔍", "ingest": "📥", "lint": "🔬", "system": "⚙️", "synthesis": "📝", "note": "📝"}

    for e in events:
        icon = icons.get(e.event_type, "•")
        date = e._date_str()[-5:] if e._date_str() else ""  # MM-DD
        line = f"- {icon} `{date}` {e.summary}"
        lines.append(line)

        # 策略 2：若超预算，截断
        current = "\n".join(lines)
        if _count(current) > max_tokens:
            # 回退：只显示最近 2 条
            short_lines = ["## 上下文记忆", ""]
            for e in events[:2]:
                icon = icons.get(e.event_type, "•")
                short_lines.append(f"- {icon} {e.summary}")
            return "\n".join(short_lines)

    return "\n".join(lines)


def build_system_prompt_suffix(user_id: str | None = None) -> str:
    """生成可注入 System Prompt 的记忆片段.

    用于在 query/ingest 操作前让 LLM 了解最近的上下文。

    Args:
        user_id: 可选筛选特定用户

    Returns:
        System Prompt 后缀文本（空字符串 = 无上下文）
    """
    events = extract_context(limit=5, user_id=user_id)
    if not events:
        return ""

    return compress_context(events)


def extract_keywords(text: str, top_k: int = 5) -> list[str]:
    """从文本中提取关键词（简单基于词频的版本）.

    用于给检索和记忆查询提供信号。不做完整 NLP，
    只提取 > 2 字的中文词或英文术语。

    Args:
        text: 输入文本
        top_k: 返回前 K 个

    Returns:
        关键词列表
    """
    # 提取中文词组（连续汉字）和英文单词
    cn_words = re.findall(r"[一-鿿]{2,}", text)
    en_words = re.findall(r"[a-zA-Z]{2,}", text)

    # 按频率排序、去重
    from collections import Counter

    word_freq = Counter(cn_words + [w.lower() for w in en_words])

    # 过滤停用词
    stopwords = {"的", "是", "了", "在", "和", "有", "不", "这", "我", "你", "他", "她", "它",
                 "the", "is", "are", "was", "were", "have", "has", "been", "this", "that"}
    filtered = [(w, c) for w, c in word_freq.most_common(top_k * 2) if w not in stopwords]

    return [w for w, _ in filtered[:top_k]]
