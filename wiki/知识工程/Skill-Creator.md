---
title: Skill-Creator
type: entity
tags: [知识工程, 工具]
aliases: [skill-creator, Skill Creator]
created: 2026-05-18
updated: 2026-05-18
sources:
  - "[[资料摘要：Agent Skill 规范构建与设计模式]]"
confidence: medium
---

> Anthropic 官方的"用来创建 Skill 的 Skill"，将 ML 工程实践（训练/测试集分割、A/B 测试、防过拟合）移植到 Prompt Engineering 领域，是目前最系统化的 Skill 开发框架。

## 概述

Skill-Creator 的设计哲学：**像做机器学习一样做 Prompt Engineering**——有训练集、测试集、评估指标、迭代优化循环、防过拟合机制。它将 CI/CD、A/B 测试、性能基准等软件工程最佳实践完整移植到 Skill 开发中。

## 关键贡献 / 特性

- **六阶段闭环**：需求捕获 → 编写 → A/B 测试 → 评估评审 → 迭代改进 → 优化与发布
- **三 Agent 协作评估体系**：Grader（评分 + 自我批评）+ Comparator（双盲比较）+ Analyzer（事后分析 + 基准聚合）
- **零依赖可移植**：纯 Python stdlib + claude CLI
- **Eval Viewer**：浏览器中可视化评审，人类判断质量
- **自举式架构**：用 Skill 框架管理 Skill 生命周期
- **打包发布**：生成 `.skill` 文件，可分享安装

## 评估体系

```
Grader Agent              Comparator Agent         Analyzer Agent
（评分者）                  （盲比较者）               （分析者）
8步评估流程                双盲设计                  事后分析 WHY 赢
自批评断言质量              内容+结构双维度评分         基准聚合统计
PASS/FAIL判定              去偏见化                   按优先级排序改进建议
```

## 已知局限

| 问题 | 详情 |
|------|------|
| Token 消耗极高 | 20 eval × 3 runs = 60 Opus 会话，单次 ~69% 5h 配额 |
| 流程冗长 | 多次确认 + 浏览器评审 + 反馈提交 |
| 子 Agent 数量多 | 3 测试 × 2(±skill) + 3 Grader + 1 Analyzer = 10+ |
| 操作型 Skill 无效 | 某些 Skill 触发率始终 0%，description 优化无效 |
| 学习曲线陡峭 | 需理解三层加载、7 种 JSON Schema、评估统计、防过拟合逻辑 |

## 相关

- [[Agent Skill]]
- [[Skill 设计模式（Google 5种）]]
- [[知识工程（Knowledge Engineering）]]
- [[Wiki 目录]]
