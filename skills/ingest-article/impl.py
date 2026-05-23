"""ingest-article 技能实现 — URL 摄取完整流水线."""

from datetime import datetime
from pathlib import Path

from knowledge_wiki.config import settings
from knowledge_wiki.wiki.paths import save_to_inbox
from knowledge_wiki.wiki.git import commit_and_push
from knowledge_wiki.wiki.builder import build_source_page, build_concept_page, extract_concept_names
from knowledge_wiki.wiki.log import append_ingest_log
from knowledge_wiki.llm.deepseek import call_ingest
from knowledge_wiki.webhook.process import fetch_url_text

WIKI_ROOT = settings.wiki_root


def execute(context: dict) -> str:
    """执行 URL 摄取流水线。

    context 需包含:
        input_text: URL 或包含 URL 的文本
        user_id: 企业微信用户 ID
        send_md: 发送 markdown 的函数
        send_tpl: 发送 template_card 的函数
    """
    text = context.get("input_text", "").strip()
    user_id = context.get("user_id", "")
    send_md = context.get("send_md")
    send_tpl = context.get("send_tpl")

    # 从文本中提取 URL
    import re
    url_match = re.search(r'https?://[^\s]+', text)
    if not url_match:
        if send_md:
            send_md(user_id, "未检测到有效 URL，请发送链接。")
        return ""
    url = url_match.group(0)

    if send_md:
        send_md(user_id, f"正在提取并分析链接内容...\n\n{url[:200]}")

    # Step 1: 下载
    raw_text = fetch_url_text(url)
    if not raw_text:
        filepath = save_to_inbox(f"待摄取：{url}", "url")
        commit_and_push(f"ingest: url ref {url[:80]}")
        if send_md:
            send_md(user_id, f"无法下载链接内容，已保存链接到 `{filepath.relative_to(WIKI_ROOT)}`")
        return ""

    # Step 2: 保存原文
    raw_file = save_to_inbox(raw_text, "url")

    # Step 3: DeepSeek 分析
    llm_data = call_ingest(raw_text, url)
    if not llm_data:
        commit_and_push(f"ingest: raw {url[:80]}")
        if send_md:
            send_md(user_id,
                f"LLM 分析失败，已保存原文到 `{raw_file.relative_to(WIKI_ROOT)}`\n请手动 `ingest`")
        return ""

    # Step 4: 构建 wiki 页面
    wiki_file = build_source_page(llm_data, url)
    new_concept_pages = []
    for c in llm_data.get("concepts", []):
        cp = build_concept_page(c)
        if cp:
            new_concept_pages.append(cp)

    page_title = llm_data.get("title", wiki_file.stem)
    append_ingest_log(llm_data, url, page_title)
    commit_and_push(f"ingest: {page_title}")

    # Step 5: 通知用户
    concept_names = extract_concept_names(llm_data.get("concepts", []))
    domain = llm_data.get("domain", "未知")
    summary = llm_data.get("summary", "")

    msg = f"已摄取到知识库\n\n**{page_title}**\n领域：{domain}\n{summary}"
    if concept_names:
        msg += f"\n新概念：{', '.join(concept_names)}"

    if send_md:
        send_md(user_id, msg)

    return ""
