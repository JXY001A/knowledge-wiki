---
title: 资料摘要：AI自主增长系统
type: source
tags: ["智能体", "架构", "最佳实践", "教程", "AI编程"]
created: 2026-05-25
updated: 2026-05-25
sources: []
confidence: medium
source_url: https://mp.weixin.qq.com/s/sZm-KDM7NoITchuhpbJkJQ
media: article
---

> 本文介绍了基于 OPC（一人公司）和 Harness Engineering 思想构建的 AI 自主增长系统。系统由多个专业 AI Agent 组成，能够自主发现增长机会、生成提案、完成从需求文档到代码实现的全程，并包含合规与质量门禁。文章详细阐述了多 Agent 架构设计、长任务保障、上下文隔离、评估独立性和 Agent 自进化机制，分享了 Benchmark 驱动的评审能力优化过程及工程化踩坑经验。

## 核心要点

- 采用多 Agent 分工架构（orchestrator、planner、builder、evaluator）实现端到端自主开发流程。
- 通过状态机、心跳监控、超时恢复和明确产出物保障长任务稳定运行。
- 拆分 planner 和 builder 为多个专业 Agent，每次任务启动新上下文以避免污染。
- 设计独立评审 Agent 体系，遵循评审与生成分离、零信任、零 Broken Feature 原则。
- 构建 Benchmark 元评估体系，用数据驱动优化评审能力，实现 Agent 自进化。
- 工程化中需重视环境一致化、标准化评审报告、保留人工部署卡点等实战问题。

## 详细笔记

## 系统背景与目标
基于高德地图 PC 站 SEO 场景，借鉴 OPC（一人公司）理念和 Harness Engineering 思想，探索让 AI 代理独立、周期性地完成发现增长机会、编写代码、测试上线的全流程。

## 系统架构设计
### 多 Agent 分工
- **Orchestrator Agent**：总控，负责调度、状态管理和日志记录。
- **Planner 拆解**：product_agent（PRD）、design_agent（UI/UX 规格）、arch_agent（技术架构、数据模型、Sprint 分解）。
- **Builder 拆解**：testcase_agent（生成测试用例）、builder_agent（功能实现，先读测试理解验收标准再写代码）。
- **Evaluator 体系**：针对不同环节设立独立评审 agent，如 proposal_reviewer、prd_reviewer、contract_reviewer、testcase_reviewer、impl_reviewer、frontend_design_reviewer，每个有自己的 prompt、技能和评分标准。

### 长任务保障机制
通过状态机定义工作流：
- 任务状态流转：DISPATCHED → ACKED → RUNNING → SUCCEEDED/FAILED。
- 心跳监控：子 Agent 须定期发心跳，orchestrator 每 60 秒检查，确认超时 300 秒，执行超时 1200 秒，超时触发重试或人工干预。
- 明确前置条件（condition）确保步骤顺序，每一步都有产出物输出和失败处理策略。

### 上下文污染隔离
- 将 planner 和 builder 按职责拆分为专业 Agent，避免单 agent 上下文爆炸。
- 每次任务启动新的 SubAgent，强制独立上下文，防止长任务中记忆混乱导致质量下降。

### 评估独立性原则
- 评审与生成彻底分离，评审员只反馈不改代码。
- 零信任，所有声明需亲自验证（如重跑测试、检查服务启动）。
- 零 Broken Feature，绝不因“只差一点点”而放行。

## Agent 自进化与 Benchmark
### 元评估体系
构建 Benchmark 评估的是“评审能力”而非代码质量。优先对 impl-reviewer 建立 Benchmark，因为其评审对象容易量化。
- **数据集层次**：
  - 代码片段：用 GitHub 优秀代码和典型缺陷制作 good/bad 示例，标注 Golden Answer。
  - 完整项目：按复杂度（todo、博客、电商）植入 OWASP/CWE 标准漏洞，不标注，零提示。
- **评审流程分层、快速失败**：
  1. 环境检查 → 依赖安装 → 编译验证 → 服务器启动 → 静态分析（ESLint、安全规则）→ 动态验证（Playwright E2E、控制台错误）。任意一步失败即终止，节省资源。
- **评分体系**：
  - 代码片段：规则遵从率 40 分、严重度加权 30 分、一致性 20 分、报告质量 10 分。
  - 完整项目：静态分析 40 分（含 Bug 检出率、精确度、安全审计等），动态验证 60 分，并乘以能力系数。
- **优化闭环**：三轮迭代后均分从 64.5 提升至 83.4，精确匹配率从 25% 到 78%，CRITICAL 漏检清零。

## 工程化踩坑与经验
- **环境工具化**：将底层业务工具（如加签算法、地图 SDK）封装为可调用技能，大幅提升 AI 调用成功率（从 10% 到近乎 100%）。
- **评审报告标准化**：要求输出 CRITICAL/MAJOR/MINOR 分类，可提前阻断，避免无效评估。
- **端到端自动化工程难题**：状态管理、超时资源管理、环境一致性、可追溯日志等工程量被严重低估。
- **保留人工部署确认**：线上最终部署仍由人工确认，因部署前后检查、回滚等风险高，人工参与可保障安全。
- **阶段性迭代**：不追求一步到位全自动，每版本确保基本通路，新问题隔离到新增部分。
- **长链路稳定性**：经过 8-10 个节点，单点成功率 90% 时端到端一次通过率不高，依赖重试和门禁回退，通常需 1-3 轮循环修复 P0 问题。

## 未来展望
- 完善数据集，覆盖 Product、Design、Arch、TestCase 等 Agent 的元评估，自建 bad/good case 和标准答案。
- OPC + AI Agent 在特定领域（如 PC 站 SEO）已可交付小团队工作，但复杂领域仍需更成熟的 Harness 框架。

## 引用与数据

当 AI Agent 拥有了强大的代码生成能力后，如何确保其输出的可靠性、一致性和长期可维护性。
评审与生成彻底分离：同一个 AI 既写又审行不通——它给自己打满分太容易了。
完全无人干预不是一个 0/1 的状态……低到一个人可以同时“监护”几十个并行运行的任务，只在少数需要判断的关键节点介入。
Benchmark 做的是“元评估”——评的不是代码写得好不好，而是 Evaluator 评得准不准。

## 相关

- [[Harness Engineering]]
- [[OPC（一人公司）]]
- [[元评估（Meta Evaluation）]]
- [[上下文隔离]]
- [[AI 多 Agent 架构设计]]
- [[Harness Engineering 实践]]
- [[OPC 一人公司工作模式]]
- [[AI 代码评审系统]]
- [[Benchmark 元评估体系]]

- [[Wiki 目录]]
