---
title: AI Workflow
type: concept
tags: [概念, 进阶]
aliases: [AI 工作流, AI工作流]
created: 2026-05-16
updated: 2026-05-16
sources:
  - "[[资料摘要：AI 日报生成器项目规划]]"
related_concepts: []
confidence: medium
---

> AI Workflow 是将多个 AI 调用、外部系统集成和异步任务编排为自动化工作流的一种架构模式。

## 是什么

AI Workflow 不是单次 AI 调用，而是将 AI 能力嵌入到多步骤的业务流程中。典型模式包括：外部触发器（GitHub webhook）→ 消息队列 → AI Worker 处理 → 结构化存储 → 前端展示。

## 为什么重要

单次 AI 调用的价值有限。真正产生业务价值的场景往往是 AI 嵌入到已有工作流中：自动分析代码提交并生成日报、自动分类工单并分配、自动生成周报/Release Note 等。

## 工作原理

```
外部事件（Commit/Issue）
    ↓
消息队列（Redis/BullMQ）
    ↓
AI Worker（Prompt + API Call）
    ↓
结构化存储（Database）
    ↓
前端展示/自动推送
```

核心组件：触发器（Webhook/OAuth 集成）→ 异步队列 → AI 处理节点 → 输出管道。

## 历史与演进

从 2023 年的单轮 Chat 应用，到 2024 年 LangChain/LlamaIndex 等框架推动 Agent 模式，到 2025 年后更加务实的 Workflow 化（将 AI 嵌入现有工程系统而非取代）。

## 常见误解

- **AI Workflow = Agent** — Agent 是 Workflow 的一种实现，但 Workflow 更强调系统集成和工程可靠性
- **Workflow 需要复杂框架** — MVP 阶段可以用简单的队列 + API 调用实现，不必引入 LangChain 等重量级框架

## 与相邻概念的区别

| 概念 | 区别 |
|------|------|
| Agent | Agent 强调自主决策循环，Workflow 强调确定性编排 |
| RAG | RAG 解决知识检索问题，Workflow 解决多步骤编排问题 |
| Pipeline | Pipeline 通常是单向数据流，Workflow 包含条件分支和人机协作节点 |

## 相关

- [[AI 日报生成器]]
- [[Wiki 目录]]
