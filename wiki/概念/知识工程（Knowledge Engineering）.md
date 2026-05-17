---
title: 知识工程（Knowledge Engineering）
type: concept
tags: [概念, 知识工程, 进阶]
aliases: [Knowledge Engineering, KE]
created: 2026-05-17
updated: 2026-05-17
sources:
  - "[[资料摘要：Agent 知识管理与自进化]]"
related_concepts: [[渐进式披露（Progressive Disclosure）]]
confidence: medium
---

> 知识工程（KE）是 Agent 时代的新兴学科，研究如何让 AI 系统高效管理、组织、更新和调用知识，与 Prompt Engineering、Context Engineering 并列为核心工程维度。

## 是什么

如果说 Prompt Engineering 是在教模型"完成什么样的任务"，那么 Knowledge Engineering 就是在教模型"应该知道什么"以及"如何运用已知信息"。它包括知识的摄入策略、结构化方法、检索机制、更新流程和生命周期管理。

## 为什么重要

知识的质量直接决定 Agent 效果的上限。Context 不仅包含对话指令和历史，更核心的是外部注入的知识。知识分为两类：

- **经验性知识**：完成特定任务所需的策略、步骤和隐性经验（如编码风格、命名规范）
- **事实性知识**：领域内的客观信息、文档、FAQ 等静态数据

## 三阶段演进

| 阶段 | 时期 | 特点 |
|------|------|------|
| 传统智能知识库 | 2016-2022 | 人工分类打标、树状标签体系、关键词匹配 |
| RAG 时代 | 2023+ | 小模型检索 + 大模型生成，但知识不沉淀 |
| Agent 时代 | 2025+ | Skillify — 知识被编译为结构化资产，一次学习永久可用 |

## 与相邻概念的区别

| 概念 | 区别 |
|------|------|
| Prompt Engineering | PE 教模型"做什么"，KE 教模型"知道什么" |
| RAG | RAG 是检索技术，KE 是涵盖摄入→组织→检索→更新的完整学科 |
| Context Engineering | CE 关注上下文组装策略，KE 关注知识本身的生命周期 |

## 相关

- [[LLM Wiki 模式]]
- [[GBrain]]
- [[渐进式披露（Progressive Disclosure）]]
- [[AI Workflow]]
- [[Wiki 目录]]
