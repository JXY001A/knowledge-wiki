# 提醒设置

设置定时提醒，到时间后通过企业微信推送通知。

## 触发条件

- 用户输入包含：提醒、闹钟、定时、几点、叫我、记得、别忘
- 或自然语言描述时间（如"明天下午3点提醒我开会"）

## 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| input_text | string | ✅ | 用户输入（含时间描述） |
| user_id | string | ✅ | 企业微信用户 ID |
| send_md | function | ✅ | 回复回调（确认和提醒推送） |

## 输出

- 即时回复：确认提醒已设置
- 延时推送：到期时推送提醒内容

## 执行步骤

1. 从 input_text 解析提醒内容、时间、重复规则
2. 调用 `remind_set` MCP 工具创建提醒
3. 启动 threading.Timer 或调度器 job
4. 到期时通过企业微信 API 推送

## 前置依赖

- `assistant.db` — SQLite 提醒存储
- `remind_set` / `remind_list` — MCP 工具
- `webhook.wechat.api.send_markdown()` — 企业微信推送
