"""评估引擎 — DeepSeek API 评分回答质量.

评分维度:
    accuracy     1-5  基于 wiki 事实的准确性
    completeness 1-5  知识覆盖的完整度
    usefulness   1-5  对用户的有用程度

返回 EvalResult，同时写入 memory_events.score。
"""

import json
import logging
import re
import urllib.request
from dataclasses import dataclass, field
from knowledge_wiki.config import settings
from knowledge_wiki.llm.base import extract_json

_log = logging.getLogger(__name__)

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"


@dataclass
class EvalResult:
    """评估结果."""
    accuracy: int = 3       # 1-5
    completeness: int = 3   # 1-5
    usefulness: int = 3     # 1-5
    overall: int = 3        # 综合（均值取整）
    gaps: list[str] = field(default_factory=list)  # 知识缺口
    improvement: str = ""   # 改进建议
    raw: str = ""           # LLM 原始输出

    @classmethod
    def from_json(cls, data: dict) -> "EvalResult":
        a = max(1, min(5, int(data.get("accuracy", 3))))
        c = max(1, min(5, int(data.get("completeness", 3))))
        u = max(1, min(5, int(data.get("usefulness", 3))))
        overall = round((a + c + u) / 3)
        return cls(
            accuracy=a, completeness=c, usefulness=u, overall=overall,
            gaps=data.get("gaps", []),
            improvement=data.get("improvement", ""),
            raw=json.dumps(data, ensure_ascii=False),
        )

    @property
    def stars(self) -> str:
        return "⭐" * self.overall

    @property
    def is_good(self) -> bool:
        return self.overall >= 4

    @property
    def has_gaps(self) -> bool:
        return len(self.gaps) > 0


EVAL_PROMPT = """你是知识库质量评估专家。根据 wiki 检索结果，评估 AI 回答的质量。

输入：
- 用户问题
- wiki 检索到的相关页面内容
- AI 生成的回答

输出 JSON（严格按此格式）：
{
  "accuracy": 1-5,
  "completeness": 1-5,
  "usefulness": 1-5,
  "gaps": ["缺失的知识点"],
  "improvement": "改进建议（≤100字）"
}

评分标准：
- accuracy: 回答是否基于 wiki 事实？有无编造？5=完全准确
- completeness: 是否覆盖了相关知识？有无遗漏重要信息？5=全面覆盖
- usefulness: 是否直接解决了用户问题？5=完美解决
- gaps: 知识库中缺失、但回答用户问题需要的知识点/概念/资料
- improvement: 简短建议如何改进回答（≤100字）

只输出 JSON，不要 markdown 代码块。"""


def evaluate_answer(question: str, answer: str, wiki_context: str = "") -> EvalResult | None:
    """调用 DeepSeek API 评估回答质量.

    Args:
        question: 用户问题
        answer: AI 生成的回答
        wiki_context: wiki 检索到的上下文

    Returns:
        EvalResult 或 None（评估失败）
    """
    api_key = settings.deepseek_api_key
    if not api_key:
        _log.warning("DEEPSEEK_API_KEY not set, skip evaluation")
        return None

    user_content = f"用户问题：{question}\n\nwiki 上下文：{wiki_context[:3000]}\n\nAI 回答：{answer[:2000]}"

    try:
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": EVAL_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 500,
        }).encode()

        req = urllib.request.Request(
            DEEPSEEK_API,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read())
            content = raw["choices"][0]["message"]["content"]

        json_str = extract_json(content)
        if not json_str:
            _log.warning("eval: no JSON in response: %s", content[:100])
            return None

        data = json.loads(json_str)
        return EvalResult.from_json(data)

    except Exception as e:
        _log.warning("eval failed: %s", e)
        return None


def evaluate_and_record(question: str, answer: str, wiki_context: str = "",
                        user_id: str = "") -> EvalResult | None:
    """评估并记录到 memory_events.score.

    Args:
        question: 用户问题
        answer: AI 回答
        wiki_context: wiki 上下文
        user_id: 用户 ID

    Returns:
        EvalResult 或 None
    """
    result = evaluate_answer(question, answer, wiki_context)
    if not result:
        return None

    # 写入记忆库
    try:
        from knowledge_wiki.memory.db import get_db, init_schema
        from knowledge_wiki.memory.models import EpisodicRecord
        from datetime import datetime, timezone

        conn = get_db()
        init_schema(conn)

        gaps_text = f"\n知识缺口：{', '.join(result.gaps)}" if result.gaps else ""

        # 尝试更新最近的 query 记录
        updated = conn.execute(
            "UPDATE memory_events SET score = ?, details = details || ? "
            "WHERE event_type = 'query' AND user_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            [result.overall, gaps_text, user_id],
        ).rowcount

        # 如果没有 query 记录，直接插入评估记录
        if updated == 0:
            record = EpisodicRecord(
                event_type="eval",
                summary=f"评估：{question[:60]}",
                details=f"问题：{question[:200]}\n回答：{answer[:200]}\n评分：{result.stars} (A{result.accuracy}/C{result.completeness}/U{result.usefulness}){gaps_text}",
                score=result.overall,
                user_id=user_id,
                source="auto",
                tags=["评估"],
            )
            d = record.to_dict()
            cols = ", ".join(d.keys())
            ph = ", ".join("?" for _ in d)
            conn.execute(f"INSERT INTO memory_events ({cols}) VALUES ({ph})", list(d.values()))

        conn.commit()
        conn.close()
    except Exception as e:
        _log.warning("eval record failed: %s", e)

    return result


def get_eval_stats() -> dict:
    """获取评估统计摘要."""
    try:
        from knowledge_wiki.memory.db import get_db, init_schema
        conn = get_db()
        init_schema(conn)

        total = conn.execute(
            "SELECT COUNT(*) FROM memory_events WHERE score IS NOT NULL"
        ).fetchone()[0]

        if total == 0:
            conn.close()
            return {"total": 0, "avg_score": 0, "by_score": {}, "message": "暂无评估数据"}

        avg = conn.execute(
            "SELECT AVG(score) FROM memory_events WHERE score IS NOT NULL"
        ).fetchone()[0]

        by_score = {}
        for r in conn.execute(
            "SELECT score, COUNT(*) as cnt FROM memory_events WHERE score IS NOT NULL "
            "GROUP BY score ORDER BY score"
        ).fetchall():
            by_score[r[0]] = r[1]

        conn.close()
        return {
            "total": total,
            "avg_score": round(avg, 1) if avg else 0,
            "by_score": by_score,
            "stars": "⭐" * round(avg) if avg else "暂无",
        }
    except Exception as e:
        _log.warning("eval stats failed: %s", e)
        return {"total": 0, "error": str(e)}
