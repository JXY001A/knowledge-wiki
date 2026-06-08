# 书签保存

保存书签 URL，自动提取网页标题和标签。

## 触发条件

- 用户输入包含：书签、收藏、稍后读、bookmark、标记
- 或发送一个 URL 并附带 "书签"、"收藏" 关键词

## 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| input_text | string | ✅ | 用户输入（含 URL） |
| user_id | string | ✅ | 企业微信用户 ID |
| send_md | function | ✅ | 回复回调 |

## 输出

通过 send_md 回复书签保存结果。

## 执行步骤

1. 从 input_text 提取 URL 和标题
2. 调用 `bookmark_add` MCP 工具保存到 SQLite
3. 格式化结果回复

## 前置依赖

- `assistant.db` — SQLite 书签存储
- `bookmark_add` / `bookmark_list` — MCP 工具
