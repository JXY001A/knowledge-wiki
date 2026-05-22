---
title: Agentic Workflow
type: concept
tags: [概念, Agent, 范式]
aliases: [工作流Agent, Workflow Agent]
created: 2026-05-22
updated: 2026-05-22
sources:
  - "[[资料摘要：Agent技术范式演变]]"
related_concepts: ["ReAct架构", "Harness", "Agent Skills体系"]
confidence: high
---

> 用工程化约束弥补模型不确定性的 Agent 架构范式，通过固定流程编排嵌入 LLM 节点，牺牲灵活性换取高可控性和可解释性。

## 是什么

Agentic Workflow 是 2024 年成为主流的 Agent 架构范式。与早期纯模型驱动的 ReAct 不同，它引入大量硬约束和流程编排：整个大框架是固定 Workflow，关键节点嵌入 LLM；或 LLM 作为中枢，调用预定义的子 Workflow。本质上是一套较重的 Harness。

代表框架：LangGraph、Dify。

## 为什么重要

- **to B 落地核心方案**：企业服务和日常重复性工作不需要真正的“智能决策”，只需按步骤保质完成
- **保证效果下限**：纯 ReAct 解决不了复杂问题，Workflow 用确定性流程兜底
- **高可控性和可解释性**：每一步可追踪、可审计
- **至今仍是主流**：大量企业在生产环境中使用

## 工作原理

1. 将业务逻辑拆解为固定的步骤序列
2. 每个步骤明确输入/输出契约
3. 仅在需要语义理解或生成的节点调用 LLM
4. 流程引擎负责编排、重试、异常处理
5. 输出经过工程化校验后再进入下一步

## 与相邻概念的区别

- **vs ReAct**：ReAct 是模型自主推理+行动循环；Workflow 是预定义流程+LLM 嵌入
- **vs 自主Agent**：自主 Agent 动态规划路径；Workflow 路径固定
- **vs Harness**：Harness 是更广义的概念，Workflow 是 Harness 的一种具体实现形态

## 相关

- [[ReAct架构]]
- [[资料摘要：Agent技术范式演变]]
- [[Harness]]
- [[Wiki 目录]]
