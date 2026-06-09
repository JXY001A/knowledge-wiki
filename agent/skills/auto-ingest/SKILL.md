# 自动摄取

根据知识缺口自动搜索并摄入资料，扩展知识库覆盖范围。

## 触发条件

- 用户输入包含：自动摄取、搜索缺口、补全知识
- 调度器触发周期扫描

## 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| input_text | string | ✅ | 用户输入或调度触发文本 |
| user_id | string | ✅ | 企业微信用户 ID |
| send_md | function | ✅ | 回复回调 |

## 输出

通过 send_md 发送缺口检测结果和自动摄入状态。

## 执行步骤

1. 调用 `evolve.gap_detector.detect_gaps()` 检测知识缺口
2. 调用 `evolve.auto_ingest.auto_ingest_topic()` 自动搜索并摄入
3. 格式化缺口列表和摄入结果
4. 通过 send_md 回复

## 前置依赖

- `evolve.gap_detector` — 知识缺口检测
- `evolve.auto_ingest` — 自动摄入模块
- `ingest-article` skill — 摄入文章引擎
