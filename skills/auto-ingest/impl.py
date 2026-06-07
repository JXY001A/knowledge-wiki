"""auto-ingest 技能实现 — 缺口搜索 + 建议 + 确认摄入."""

import re


def execute(context: dict) -> str:
    """搜索知识缺口文章并建议摄入.

    输入: "自动摄取" → 返回建议列表
          "摄取 <编号>" → 摄入指定文章
          "摄取全部" → 摄入所有建议
    """
    from knowledge_wiki.evolve.auto_ingest import suggest_ingest, auto_ingest_topic, suggest_markdown

    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    text = context.get("input_text", "").strip()

    # 判断意图
    if any(kw in text for kw in ["摄取全部", "全部摄入"]):
        data = suggest_ingest()
        suggestions = data.get("suggestions", [])
        if not suggestions:
            msg = "未发现可摄取的文章。"
        else:
            results = []
            for s in suggestions[:5]:
                r = auto_ingest_topic(s.topic, s.url)
                results.append(r)
            msg = f"已自动摄取 {len(results)} 篇文章：\n\n" + "\n".join(results[:5])

    elif m := re.search(r"摄取\s*(\d+)", text):
        idx = int(m.group(1)) - 1
        data = suggest_ingest()
        suggestions = data.get("suggestions", [])
        if 0 <= idx < len(suggestions):
            s = suggestions[idx]
            msg = auto_ingest_topic(s.topic, s.url)
        else:
            msg = f"无效编号，共 {len(suggestions)} 篇文章可选。"

    else:
        msg = suggest_markdown()

    if send_md:
        send_md(user_id, msg[:3000])
    return msg
