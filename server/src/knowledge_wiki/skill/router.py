"""多模型路由 — 根据任务复杂度将请求分发到本地模型或 DeepSeek API."""

from knowledge_wiki.skill.registry import Skill


def select_model(skill: Skill | None, intent: str = "") -> str:
    """选择执行模型.

    优先级：skill.json 中的 model 字段 > 基于意图的自动判断.

    Returns:
        "local" | "deepseek"
    """
    if skill and skill.model != "auto":
        return skill.model

    # 自动判断：复杂任务 → DeepSeek，简单任务 → local
    complex_keywords = ["ingest", "分析", "总结", "长篇", "生成", "复杂", "综合"]
    if any(kw in intent for kw in complex_keywords):
        return "deepseek"

    return "local"


def get_model_config(model_type: str) -> dict:
    """获取模型配置."""
    if model_type == "deepseek":
        return {
            "model": "deepseek-v4-pro",
            "endpoint": "https://api.deepseek.com/v1/chat/completions",
            "max_tokens": 4096,
            "temperature": 0.1,
        }
    return {
        "model": "qwen2.5:3b",
        "endpoint": "http://localhost:11434/api/chat",
        "max_tokens": 2000,
        "temperature": 0.1,
    }
