# ingest-article

摄取文章 URL，自动执行下载 → LLM 分析 → wiki 页面生成 → 操作日志 → Git 同步的完整流水线。

## 触发条件

- 用户输入为 http/https URL
- 或输入包含：摄取、ingest、整理、收录、分析这篇文章
- 或企业微信发送纯 URL

## 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| input_text | string | ✅ | 文章 URL |
| user_id | string | ✅ | 企业微信用户 ID |
| send_md | callable | ✅ | 发送 markdown 消息的函数 |
| send_tpl | callable | ✅ | 发送 template_card 消息的函数 |

## 输出

企业微信回复：摘要卡片（标题 + 领域 + 新概念列表）。

## 执行步骤

1. 下载 URL → 提取可读文本（`fetch_url_text()`）
2. 保存原文到 `raw/收件箱/`
3. DeepSeek API 分析 → 结构化 JSON（`llm.deepseek.call_ingest()`）
4. 创建 `wiki/资料摘要/` 页面（`wiki.builder.build_source_page()`）
5. 创建 `wiki/概念/` 页面（`wiki.builder.build_concept_page()`）
6. 更新操作日志（`wiki.log.append_ingest_log()`）
7. Git commit + push

## 前置依赖

- `webhook.process.fetch_url_text()` — URL 下载与文本提取
- `llm.deepseek.call_ingest()` — DeepSeek API 分析
- `wiki.builder` — wiki 页面生成
- `wiki.git` — Git 同步

## 评估标准

- 正确性：wiki 页面符合 AGENTS.md 模板规范
- 完整性：资料摘要 + 概念页 + 交叉引用全部生成
- 响应速度：< 120s（含 DeepSeek API 调用）
