---
title: Agent Skills体系
type: concept
tags: [概念, Agent, 范式, 最佳实践]
aliases: [Skill体系, Agent Skills]
created: 2026-05-22
updated: 2026-05-22
sources:
  - "[[资料摘要：Agent技术范式演变]]"
  - "[[Agent Skill]]"
related_concepts: ["渐进式披露", "上下文工程", "Agentic Workflow"]
confidence: high
---

> 将执行特定任务的方法论、步骤、约束和脚本封装为可复用的模块化技能包（SKILL.md），Agent 通过渐进式披露按需加载对应技能文件获取操作指南。

## 是什么

Agent Skills 体系是 Agent 上下文工程的核心组成部分。将原本堆积在 System Prompt 中的大量具体任务要求、领域知识、人设规范等“动态内容”，拆解并存储到外部文件系统中（如 SKILL.md），Agent 在执行特定任务时动态加载。当前 Agent 系统的 System Prompt 只保留最底层、最通用的系统级指令和基本行为规范。

## 为什么重要

- **降低维护复杂度**：不再为每个任务写“小作文”级别的 System Prompt
- **模块化复用**：一个 Skill 可被多个 Agent 或多个场景复用
- **渐进式披露**：只加载当前任务需要的 Skill，节省 ~90% 上下文
- **可版本管理**：Skill 文件纳入 Git 追踪，支持回滚和效果对比
- **从“调参”到“工程”**：Agent 开发从 prompt 调试转向模块化工程

## 工作原理

1. 将任务方法论、步骤要求、领域约束沉淀为 SKILL.md 文件
2. System Prompt 只保留通用指令 + Skill 使用方式说明
3. Agent 识别任务意图 → 匹配对应 Skill → 动态加载文件内容
4. 执行完成后释放上下文，等待下一个任务

## 与相邻概念的区别

- **vs Prompt Engineering**：Prompt 是直接写指令；Skill 是结构化、模块化的指令包
- **vs Workflow**：Workflow 是执行流程的编排；Skill 是能力的封装
- **vs MCP Tool**：MCP Tool 是外部工具接口；Skill 是对工具使用方法和领域知识的封装

## 相关

- [[Agent Skill]]
- [[渐进式披露]]
- [[资料摘要：Agent技术范式演变]]
- [[Skill 设计模式（Google 5种）]]
- [[Wiki 目录]]
