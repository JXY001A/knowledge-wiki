"""消息处理 — 分发(? query / URL ingest / 文本保存)."""

import html as html_mod
import json
import re
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

from knowledge_wiki.config import settings
from knowledge_wiki.wiki.paths import save_to_inbox
from knowledge_wiki.wiki.git import commit_and_push
from knowledge_wiki.wiki.frontmatter import strip_frontmatter
from knowledge_wiki.wiki.builder import build_source_page, build_concept_page, extract_concept_names
from knowledge_wiki.wiki.log import append_ingest_log
from knowledge_wiki.wiki.search import keyword_search, get_top_page_titles
from knowledge_wiki.llm.deepseek import call_ingest
from knowledge_wiki.llm.ollama import call_json, call_short
from knowledge_wiki.mcp.client import mcp_query

WIKI_ROOT = settings.wiki_root


# ---- URL 处理 ----

def is_url(text: str) -> bool:
    """检查文本是否为 http/https URL."""
    return bool(re.match(r'^https?://[^\s]+$', text))


def fetch_url_text(url: str) -> str | None:
    """下载 URL 内容并提取可读文本."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; KnowledgeBot/1.0)"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            html_data = resp.read().decode("utf-8", errors="ignore")

        if "text/plain" in content_type or "text/markdown" in content_type:
            return html_data

        # 提取标题: og:title > h1 > <title>
        title = ""
        for pattern in [
            r'<meta\s+property="og:title"\s+content="(.*?)"',
            r'<h1[^>]*?id="activity-name"[^>]*>(.*?)</h1>',
            r"<h1[^>]*>(.*?)</h1>",
            r"<title>(.*?)</title>",
        ]:
            m = re.search(pattern, html_data, re.IGNORECASE | re.DOTALL)
            if m:
                title = html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip())
                if title:
                    break
        if not title:
            title = url

        # 移除 script, style, nav, footer, header
        for tag in ["script", "style", "nav", "footer", "header"]:
            html_data = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", html_data, flags=re.DOTALL | re.IGNORECASE)

        # 剥离 HTML 标签
        text = re.sub(r"<[^>]+>", "\n", html_data)
        text = html_mod.unescape(text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        if len(text) > 50000:
            text = text[:50000] + "\n\n...(内容已截断)"

        return f"# {title}\n\n- 来源: {url}\n- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{text.strip()}"
    except Exception as e:
        print(f"[wecom] fetch URL failed: {e}", flush=True)
        return None


# ---- 消息处理 ----

def handle_url_ingest(user_id: str, url: str, send_md, send_tpl):
    """自动摄取 URL: 下载 → LLM 分析 → wiki 页面 → 日志 → git push."""
    send_md(user_id, f"正在提取并分析链接内容...\n\n{url[:200]}")

    raw_text = fetch_url_text(url)
    if not raw_text:
        filepath = save_to_inbox(f"待摄取：{url}", "url")
        commit_and_push(f"ingest: url ref {url[:80]}")
        send_md(user_id, f"无法下载链接内容，已保存链接到 `{filepath.relative_to(WIKI_ROOT)}`")
        return

    raw_file = save_to_inbox(raw_text, "url")

    llm_data = call_ingest(raw_text, url)
    if not llm_data:
        commit_and_push(f"ingest: raw {url[:80]}")
        send_md(user_id, f"LLM 分析失败，已保存原文到 `{raw_file.relative_to(WIKI_ROOT)}`\n请手动 `ingest`")
        return

    wiki_file = build_source_page(llm_data, url)
    new_concept_pages = []
    for c in llm_data.get("concepts", []):
        cp = build_concept_page(c)
        if cp:
            new_concept_pages.append(cp)

    page_title = llm_data.get("title", wiki_file.stem)
    append_ingest_log(llm_data, url, page_title)

    commit_and_push(f"ingest: {page_title}")

    concept_names = extract_concept_names(llm_data.get("concepts", []))
    domain = llm_data.get("domain", "未知")
    summary = llm_data.get("summary", "")
    msg = f"已摄取到知识库\n\n**{page_title}**\n领域：{domain}\n{summary}"
    if concept_names:
        msg += f"\n新概念：{', '.join(concept_names)}"
    send_md(user_id, msg)


def handle_query_msg(user_id: str, question: str, send_md, send_tpl):
    """MCP 检索 → qwen2.5:3b → 结构化 template_cards."""
    context = mcp_query(question)
    if not context:
        send_md(user_id, "知识库查询失败，请重试。")
        return

    context = strip_frontmatter(context)

    card_data = call_json(question, context)
    if not card_data or "cards" not in card_data:
        # Fallback: 关键字搜索
        results = keyword_search(question)
        if not results:
            send_md(user_id, f"知识库中暂无「{question}」相关内容。")
            return
        score, title, filepath = results[0]
        body = filepath.read_text()
        body_text = strip_frontmatter(body)
        send_tpl(user_id,
            title=title,
            summary=_extract_first_meaningful_text(body_text),
            details=_extract_kv_from_markdown(body_text) or _extract_section_kv(body_text),
            source_desc=title)
        return

    cards = card_data["cards"]
    top_page = get_top_page_titles(question)
    for i, card in enumerate(cards[:8]):
        if i > 0:
            time.sleep(0.8)
        details = _normalize_details(card.get("details", []))
        summary = card.get("summary", "")
        if not summary:
            summary = call_short(f"{card.get('title', question)} 的核心信息",
                                 json.dumps(details, ensure_ascii=False))
        send_tpl(user_id,
            title=card.get("title", question),
            summary=summary or "",
            details=details,
            source_desc=f"{top_page} ({i + 1}/{len(cards)})")

    overall = card_data.get("summary", "")
    if overall and len(overall) > 100:
        clean = _clean_markdown(overall)
        if len(clean) > 50:
            send_md(user_id, clean)


def handle_inbox_text(user_id: str, text: str, send_md):
    """保存文本到 raw/收件箱."""
    filepath = save_to_inbox(text, "text")
    commit_and_push(f"ingest: wecom text {filepath.name}")
    send_md(user_id, f"已保存到知识库\n\n> 文件：`{filepath.relative_to(WIKI_ROOT)}`\n> 可在 Obsidian 或 MCP 中处理 ingest")


def process_message(user_id: str, text: str, send_md, send_tpl):
    """处理收到的消息 — 通过 Skill 引擎路由分发.

    流程：
    1. 提取意图（? 查询、URL、纯文本）
    2. 技能引擎匹配最合适的 Skill
    3. 执行 Skill 的 impl.py
    4. Skill 内部通过 send_md / send_tpl 回调回复用户
    """
    from knowledge_wiki.skill.engine import match_skill
    from knowledge_wiki.skill.planner import execute_skill

    try:
        stripped = text.strip()

        # 构建执行上下文
        ctx = {
            "user_id": user_id,
            "input_text": stripped,
            "send_md": send_md,
            "send_tpl": send_tpl,
        }

        # 意图 → 技能匹配
        skill = None

        if stripped.startswith("?"):
            question = stripped[1:].strip()
            if not question:
                send_md(user_id, "请输入查询内容，如：`? DevMechin GPU`")
                return
            ctx["query"] = question
            skill = match_skill(question)

        elif is_url(stripped):
            skill = match_skill(stripped)

        else:
            # 纯文本：尝试匹配显式触发词，否则回退到 save-note
            skill = match_skill(stripped)  # "记录" "保存" → save-note

        # 技能回退链
        if not skill:
            if stripped.startswith("?"):
                # query-knowledge 作为 ? 查询的兜底
                execute_skill("query-knowledge", ctx)
            elif is_url(stripped):
                execute_skill("ingest-article", ctx)
            else:
                execute_skill("save-note", ctx)
        else:
            result = execute_skill(skill.name, ctx)
            # 某些技能通过回调发送消息（send_md），不需要返回文本
            # 如果 execute 返回非空文本且没有 send_md，则用 send_md 发送
            if result and result.strip() and not ctx.get("_handled"):
                send_md(user_id, result[:3000])

    except Exception as e:
        print(f"[wecom] process error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        send_md(user_id, "处理消息时出错，请重试。")


# ---- 提取辅助函数 ----

def _normalize_details(raw: list) -> list[tuple[str, str]]:
    """标准化 LLM details 输出为 template_card horizontal_content_list."""
    if not raw:
        return []

    result = []
    for item in raw:
        if isinstance(item, (list, tuple)):
            if len(item) >= 2:
                result.append((str(item[0])[:20], str(item[1])[:60]))
        elif isinstance(item, dict):
            cn_key = item.get("键") or item.get("key") or item.get("name")
            cn_val = item.get("值") or item.get("value") or item.get("val")
            if cn_key and cn_val is not None:
                result.append((str(cn_key)[:20], str(cn_val)[:60]))
            else:
                for k, v in item.items():
                    if k not in ("键", "值", "key", "value", "name", "val"):
                        result.append((str(k)[:20], str(v)[:60]))
        elif isinstance(item, str):
            result.append(("", str(item)[:60]))

    if not result and all(isinstance(x, str) for x in raw):
        for i in range(0, len(raw) - 1, 2):
            result.append((str(raw[i])[:20], str(raw[i + 1])[:60]))

    return result[:10]


def _extract_first_meaningful_text(body: str) -> str:
    """提取 wiki 页面第一个有意义的段落作为卡片描述."""
    lines = body.strip().split("\n")
    text_lines = []
    for line in lines:
        s = line.strip()
        if not s:
            if text_lines:
                break
            continue
        if s.startswith("> "):
            text_lines.append(s[2:])
        elif not s.startswith("#") and not s.startswith("|") and not s.startswith("```"):
            text_lines.append(s)
        if len(" ".join(text_lines)) > 200:
            break
    return " ".join(text_lines)[:300]


def _extract_kv_from_markdown(body: str) -> list[tuple[str, str]]:
    """从 markdown 表格中提取 key-value 对."""
    pairs = []
    lines = body.split("\n")
    headers = []

    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            headers = []
            continue

        if re.match(r"^[\s|:\-]+$", s):
            continue

        cells = [c.strip() for c in s.strip("|").split("|")]
        if not headers and len(cells) >= 2:
            headers = cells
        elif headers and len(cells) == len(headers):
            for h, v in zip(headers, cells):
                if h and v and h not in ("---", ":", "-"):
                    pairs.append((h, v))
            break

    return pairs[:6]


def _extract_section_kv(body: str) -> list[tuple[str, str]]:
    """Fallback: 使用 ## section 标题作为隐式 key-value."""
    sections = re.split(r"\n##\s+", body)
    pairs = []
    for sec in sections[1:]:
        header_end = sec.find("\n")
        if header_end == -1:
            continue
        key = sec[:header_end].strip()
        rest = sec[header_end:].strip()
        first_line = rest.split("\n")[0].strip()
        if len(first_line) > 5 and len(first_line) < 80:
            pairs.append((key, first_line))
        if len(pairs) >= 6:
            break
    return pairs


def _clean_markdown(text: str) -> str:
    """清理 LLM markdown 以适配企业微信显示."""
    text = re.sub(r"```[\s\S]*?```", lambda m: "[代码]", text)
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        s = line.strip()
        if re.match(r"^[\s|:\-]+$", s):
            continue
        cleaned.append(line)
    text = "\n".join(cleaned)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
