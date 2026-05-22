---
title: Agent Skill
type: concept
tags: [概念, 知识工程, 基础]
aliases: [Skill, Agent Skills]
created: 2026-05-18
updated: 2026-05-18
sources:
  - "[[资料摘要：Agent Skill 规范构建与设计模式]]"
related_concepts: [[渐进式披露]]
confidence: high
---

> Agent Skill 是一种可复用的 Prompt 增强包，通过渐进式加载机制为 Agent 注入领域知识和工作流程——它不是 Prompt，而是围绕任务、工具、流程和输出边界的结构化行为设计。

## 是什么

一个 Skill 的最小形态只有一个 `SKILL.md` 文件（YAML frontmatter + Markdown 正文），可选配 `scripts/`、`references/`、`assets/` 子目录。2025 年 12 月，Anthropic 将其作为开放标准发布（[agentskills.io](https://agentskills.io/specification)），已获 33+ Agent 产品采纳。

## 为什么重要

Skill 解决了 Agent 系统的核心矛盾：**知识越多，上下文越膨胀**。三层渐进式加载（L1 目录 → L2 指令 → L3 资源）让 20 个 Skill 的初始加载仅需 1000-2000 tokens，相比单体式 prompt 减少约 90%。

## 工作原理

```
L1 启动时：只注入所有 Skill 的 name + description（XML 格式）
    ↓ 用户任务匹配某 Skill 的 description
L2 激活时：Agent 读取完整 SKILL.md body（<500 行）
    ↓ 指令引用外部文件
L3 按需时：读取 scripts/、references/、assets/ 中的特定文件
```

触发机制是 **Model-driven Activation**：description 字段决定何时激活，模型自主判断匹配，非关键词硬编码。

## 核心原则

| 原则 | 说明 |
|------|------|
| 触发不总结工作流 | description 只写触发条件，不概括步骤（否则 Agent 走捷径） |
| 简洁优先 | 默认 Agent 已聪明，只加它不知道的 |
| 自由度分层 | 高（代码审查）/ 中（模板）/ 低（数据库迁移） |
| 解释 WHY | 不堆砌 ALWAYS/NEVER，解释为什么某件事重要 |

## 历史与演进

2025 年 12 月 Anthropic 发布规范 → 2026 年 33+ Agent 产品支持 → 开源市场涌现（skills.sh、clawhub 等）→ Skill Bench 评测体系出现。

## 与相邻概念的区别

| 概念 | 区别 |
|------|------|
| Prompt | Prompt 是单次指令，Skill 是带元数据的结构化可复用包 |
| MCP Tool | Tool 是执行能力，Skill 是知识+流程+工具组合的行为设计 |
| LLM Wiki 页面 | Wiki 页面存储"是什么"，Skill 定义"怎么做" |

## 相关

- [[渐进式披露]]
- [[Skill-Creator]]
- [[Skill 设计模式（Google 5种）]]
- [[知识工程（Knowledge Engineering）]]
- [[Wiki 目录]]
