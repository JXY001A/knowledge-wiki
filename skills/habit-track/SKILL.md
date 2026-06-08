# 习惯追踪

记录每日习惯完成情况，支持打卡、连续统计和趋势查看。

## 触发条件

- 用户输入包含：打卡、习惯、habit
- 或匹配习惯名称直接打卡（如"喝水"、"运动"）

## 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| input_text | string | ✅ | 用户输入（习惯名或打卡指令） |
| user_id | string | ✅ | 企业微信用户 ID |
| send_md | function | ✅ | 回复回调 |

## 输出

通过 send_md 发送打卡结果或习惯统计。

## 执行步骤

1. 解析用户意图（打卡/创建/统计）
2. 调用 `habit_create`、`habit_log`、`habit_stats` MCP 工具
3. 格式化结果回复

## 前置依赖

- `assistant.db` — SQLite 习惯存储
- `habit_create` / `habit_log` / `habit_stats` — MCP 工具
