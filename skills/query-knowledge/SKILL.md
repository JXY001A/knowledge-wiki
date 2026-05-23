# query-knowledge

基于 wiki 知识库回答用户问题。通过 MCP 检索相关页面，调用本地 LLM 综合生成结构化回答。

## 触发条件

- 用户输入以 `?` 开头且包含：是什么、怎么、为什么、介绍、解释、说明、对比
- 或输入以 `?` 开头且无法匹配其他技能时作为默认查询技能

## 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| input_text | string | ✅ | 用户问题（去掉 ? 前缀） |
| user_id | string | ✅ | 企业微信用户 ID |
| send_md | callable | ✅ | 发送 markdown 消息的函数 |
| send_tpl | callable | ✅ | 发送 template_card 消息的函数 |

## 输出

结构化 template_card 回复（2-5 张卡片），包含分类标题、摘要、详细信息键值对。

## 执行步骤

1. 去掉 `?` 前缀提取问题文本
2. 调用 `mcp.client.mcp_query(question)` 检索 wiki
3. 调用 `llm.ollama.call_json(question, context)` 生成结构化 JSON
4. 解析 JSON → 构建 template_cards
5. 依次发送卡片 + 综合 markdown

## 前置依赖

- `mcp.client.mcp_query()` — MCP 知识检索
- `llm.ollama.call_json()` — qwen2.5:3b 结构化输出
- `webhook.wechat.api.send_template_card()` — 企业微信卡片消息

## 评估标准

- 准确性：回答基于 wiki 事实，不编造
- 完整性：覆盖所有相关知识点
- 响应速度：< 30s
