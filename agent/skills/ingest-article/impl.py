"""
ingest-article 技能实现 — URL 摄取完整流水线。

本模块实现从 URL 到知识库页面的端到端自动化流水线：
    1. 识别并提取用户消息中的 URL
    2. 下载网页内容（通过 webhook.process.fetch_url_text）
    3. 保存原始文本到 raw/收件箱/（不可变源文档）
    4. 调用 DeepSeek LLM 分析内容，提取结构化元数据
    5. 构建 wiki 页面（资料摘要页 + 概念页）
    6. 追加操作日志 + git 提交推送
    7. 通过企业微信通知用户摄取结果

整个流水线严格遵循 AGENTS.md 中定义的 ingest 操作规范：
    - 原始文本存入 raw/ 层（只读不写）
    - LLM 生成的内容存入 wiki/ 层
    - 每次操作后自动 git commit & push
"""

# ---------------------------------------------------------------------------
# 标准库导入
# ---------------------------------------------------------------------------
from datetime import datetime  # 日期时间处理（当前未直接使用，由下游模块使用）
from pathlib import Path        # 路径对象，用于相对路径计算

# ---------------------------------------------------------------------------
# 项目内部导入
# ---------------------------------------------------------------------------
from knowledge_wiki.config import settings              # 全局配置单例（wiki_root, LLM 密钥等）
from knowledge_wiki.wiki.paths import save_to_inbox     # 将文本保存到 raw/收件箱/，返回文件 Path
from knowledge_wiki.wiki.git import commit_and_push     # git add -A → commit → push 原子操作
from knowledge_wiki.wiki.builder import (
    build_source_page,        # 使用 LLM 数据构建 wiki/资料摘要/ 页面
    build_concept_page,       # 使用 LLM 提取的概念构建 wiki/概念/ 页面
    extract_concept_names,    # 从概念数据列表提取概念名称（用于通知消息）
)
from knowledge_wiki.wiki.log import append_ingest_log   # 追加操作日志到 wiki/操作日志.md
from knowledge_wiki.llm.deepseek import call_ingest     # 调用 DeepSeek API 对原始文本做结构化分析
from knowledge_wiki.webhook.process import fetch_url_text  # 下载并清洗 URL 内容为纯文本

# ---------------------------------------------------------------------------
# 常量：知识库根目录（从配置读取）
# ---------------------------------------------------------------------------
# WIKI_ROOT 用于计算相对路径，在通知消息中展示文件位置
WIKI_ROOT = settings.wiki_root


def execute(context: dict) -> str:
    """执行 URL 摄取流水线的入口函数，由技能路由系统调用。

    本函数是 ingest-article skill 的唯一公开接口，负责编排从 URL 到 wiki
    页面入库的完整流程。所有步骤在同一个函数调用中完成，失败时尽早返回并
    通知用户当前进度。

    流水线阶段：
        Step 0 — URL 识别：正则提取用户消息中的第一个 URL
        Step 1 — 内容下载：fetch_url_text 拉取并清洗网页
        Step 2 — 原文存档：save_to_inbox 写入 raw/收件箱/
        Step 3 — LLM 分析：call_ingest 调用 DeepSeek 提取结构化元数据
        Step 4 — 页面构建：build_source_page + build_concept_page
        Step 5 — 用户通知：通过企业微信发送摄取结果摘要

    Args:
        context: 技能上下文字典，由路由系统注入，包含以下键：
            input_text (str): 用户发送的消息文本，可能包含 URL
            user_id (str): 企业微信用户 ID，用于定向回复
            send_md (Callable[[str, str], None] | None):
                发送 Markdown 消息的函数，签名为 send_md(user_id, content)。
                为 None 时跳过消息推送（如在非交互场景）。
            send_tpl (Callable | None):
                发送模板卡片消息的函数，当前流水线未使用，保留以备扩展。

    Returns:
        str: 始终返回空字符串 ""。实际结果通过 send_md 推送企业微信消息通知用户。
             返回空串是为了兼容技能系统的统一返回约定。
    """
    # ------------------------------------------------------------------
    # 解析上下文参数
    # ------------------------------------------------------------------
    text = context.get("input_text", "").strip()  # 用户原始消息文本
    user_id = context.get("user_id", "")           # 企业微信用户 ID
    send_md = context.get("send_md")               # Markdown 消息发送函数（可能为 None）
    send_tpl = context.get("send_tpl")             # 模板消息发送函数（保留，当前未使用）

    # ------------------------------------------------------------------
    # Step 0: 从文本中提取 URL
    # ------------------------------------------------------------------
    # 使用正则匹配 http/https 协议的完整 URL，取第一个匹配项。
    # 正则说明：[^\s]+ 匹配任意非空白字符序列，直到遇到空格、换行或文本结束。
    import re  # 局部导入：只在需要 URL 解析时加载 re 模块，减少顶层开销
    url_match = re.search(r'https?://[^\s]+', text)
    if not url_match:
        # 未检测到 URL 时立即反馈用户，提前退出避免无效处理
        if send_md:
            send_md(user_id, "未检测到有效 URL，请发送链接。")
        return ""
    url = url_match.group(0)

    # 通知用户流水线已启动（截取前 200 字符避免 URL 过长刷屏）
    if send_md:
        send_md(user_id, f"正在提取并分析链接内容...\n\n{url[:200]}")

    # ------------------------------------------------------------------
    # Step 1: 下载网页内容（清洗为纯文本）
    # ------------------------------------------------------------------
    # fetch_url_text 内部流程：
    #   1. defuddle/requests 下载网页 HTML
    #   2. 去除导航、广告、脚本等非正文内容
    #   3. 返回干净的 Markdown/纯文本
    # 失败时返回空字符串，此时仅保存 URL 引用到收件箱。
    raw_text = fetch_url_text(url)
    if not raw_text:
        # 下载失败：保存 URL 裸引用到收件箱，标记为 "待摄取"
        filepath = save_to_inbox(f"待摄取：{url}", "url")
        # git 提交记录 URL 引用（截取前 80 字符作为 commit message）
        commit_and_push(f"ingest: url ref {url[:80]}")
        if send_md:
            send_md(user_id,
                     f"无法下载链接内容，已保存链接到 `{filepath.relative_to(WIKI_ROOT)}`")
        return ""

    # ------------------------------------------------------------------
    # Step 2: 保存原始文本到 raw/收件箱/（不可变层）
    # ------------------------------------------------------------------
    # save_to_inbox 将清洗后的文本写入 raw/收件箱/ 目录，文件名由内容摘要生成。
    # 此步骤确保原始资料在 LLM 分析前已完成持久化，分析失败也不丢原文。
    # 文件类型标记为 "url"，帮助下游区分来源。
    raw_file = save_to_inbox(raw_text, "url")

    # ------------------------------------------------------------------
    # Step 3: 调用 DeepSeek LLM 分析内容（结构化提取）
    # ------------------------------------------------------------------
    # call_ingest 向 DeepSeek API 发送原始文本，要求 LLM：
    #   1. 生成文章标题（title）
    #   2. 撰写 1-2 句摘要（summary）
    #   3. 判断所属知识领域（domain）
    #   4. 提取核心概念列表（concepts），每个概念含定义和解释
    #   5. 返回结构化 JSON，由调用方解析
    # 失败时返回 None 或空 dict，此时原文已保存，用户可手动触发 ingest。
    llm_data = call_ingest(raw_text, url)
    if not llm_data:
        # LLM 分析失败：原文已安全落盘，提交并通知用户手动处理
        commit_and_push(f"ingest: raw {url[:80]}")
        if send_md:
            send_md(user_id,
                f"LLM 分析失败，已保存原文到 `{raw_file.relative_to(WIKI_ROOT)}`\n请手动 `ingest`")
        return ""

    # ------------------------------------------------------------------
    # Step 4: 构建 wiki 页面（LLM 维护层）
    # ------------------------------------------------------------------
    # 4a. 构建资料摘要页（wiki/资料摘要/）
    #     build_source_page 将 LLM 分析结果写入模板化的 source 类型页面，
    #     包含 frontmatter、摘要、概念列表、来源链接等。
    wiki_file = build_source_page(llm_data, url)

    # 4b. 为每个新提取的概念构建概念页（wiki/概念/）
    #     遍历 LLM 返回的概念列表，调用 build_concept_page 逐个创建。
    #     若概念页已存在，build_concept_page 返回 None（跳过不重复创建）。
    new_concept_pages = []
    for c in llm_data.get("concepts", []):
        cp = build_concept_page(c)
        if cp:
            new_concept_pages.append(cp)

    # 4c. 追加操作日志到 wiki/操作日志.md
    #     记录本次 ingest 的元信息：标题、URL、时间、新建页面等。
    #     若 LLM 未返回标题，降级使用 wiki 文件的 stem（文件名去扩展名）。
    page_title = llm_data.get("title", wiki_file.stem)
    append_ingest_log(llm_data, url, page_title)

    # 4d. git 提交并推送所有变更
    #     commit_and_push 执行 git add -A → git commit → git push，
    #     将 raw/ + wiki/ 的所有变更一次性同步到 GitHub。
    commit_and_push(f"ingest: {page_title}")

    # ------------------------------------------------------------------
    # Step 5: 构造并发送企业微信通知消息
    # ------------------------------------------------------------------
    # 从 LLM 分析结果中提取通知摘要所需的信息：
    concept_names = extract_concept_names(llm_data.get("concepts", []))  # 概念名称列表
    domain = llm_data.get("domain", "未知")                               # 所属领域
    summary = llm_data.get("summary", "")                                 # 文章摘要

    # 组装 Markdown 通知消息
    msg = f"已摄取到知识库\n\n**{page_title}**\n领域：{domain}\n{summary}"
    if concept_names:
        # 若有新概念，附加到消息末尾供用户快速查看
        msg += f"\n新概念：{', '.join(concept_names)}"

    if send_md:
        send_md(user_id, msg)

    # 返回空字符串：实际结果已通过企业微信消息推送，无需返回值。
    return ""
