# save-note

将文本保存到 raw/收件箱/，作为后续 ingest 的原料。这是消息处理的默认回退技能（当无其他技能匹配时使用）。

## 触发条件

- 用户输入不匹配任何其他技能
- 或显式包含：保存、记录、笔记、save、note

## 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| input_text | string | ✅ | 要保存的文本内容 |
| user_id | string | ✅ | 企业微信用户 ID |
| send_md | callable | ✅ | 发送 markdown 消息的函数 |

## 输出

确认消息，包含保存的文件路径。

## 执行步骤

1. 保存内容到 `raw/收件箱/wecom-text-{timestamp}.md`
2. Git commit + push
3. 返回确认消息

## 前置依赖

- `wiki.paths.save_to_inbox()` — 文件保存
- `wiki.git.commit_and_push()` — 同步
