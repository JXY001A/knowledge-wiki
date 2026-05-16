---
title: 资料摘要：DeepSeek API 定价
type: source
tags: [deepseek, 资讯, 易过时]
created: 2026-05-16
updated: 2026-05-16
sources:
  - "[[DeepSeek]]"
confidence: high
source_url: https://api-docs.deepseek.com/zh-cn/quick_start/pricing
media: article
---

> DeepSeek 当前模型（V4-Flash、V4-Pro）的定价详情与扣费规则。V4-Pro 处于 2.5 折优惠期至 2026/05/31。

## 核心要点

- DeepSeek 当前提供两个模型：**deepseek-v4-flash**（轻量）和 **deepseek-v4-pro**（旗舰）
- 两个模型均支持 1M 上下文、384K 最大输出、思考模式、JSON 输出、Tool Calls
- V4-Pro 当前 2.5 折，优惠截止 2026/05/31；缓存命中价格低至 0.025 元/百万 tokens
- 全系列缓存命中价格已降至首发价格的 1/10（2026/4/26 起生效）
- 兼容 OpenAI 和 Anthropic 两种 API 格式
- 旧模型名 `deepseek-chat` 和 `deepseek-reasoner` 即将弃用

## 详细笔记

### 模型对比

| 维度 | V4-Flash | V4-Pro |
|------|----------|--------|
| 缓存命中 | 0.02 元 | 0.025 元（2.5 折）|
| 缓存未命中 | 1 元 | 3 元（2.5 折）|
| 输出 | 2 元 | 6 元（2.5 折）|
| 上下文 | 1M | 1M |
| 最大输出 | 384K | 384K |
| FIM 补全 | 仅非思考模式 | 仅非思考模式 |

### 价格变动节点

- **2026/4/26**：全系列缓存命中降至 1/10
- **2026/05/31 23:59**：V4-Pro 2.5 折优惠到期，届时恢复原价（输入缓存命中 0.1 元、缓存未命中 12 元、输出 24 元）

## 引用与数据

- 价格单位：元/百万 tokens
- 扣费公式：token 消耗量 × 模型单价
- 余额消耗顺序：赠送余额 > 充值余额

## 相关

- [[DeepSeek]]
- [[Wiki 目录]]
