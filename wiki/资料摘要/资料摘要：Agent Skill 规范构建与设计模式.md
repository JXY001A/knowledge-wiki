---
title: 资料摘要：Agent Skill 规范构建与设计模式
type: source
tags: [知识工程, 教程, 最佳实践, 长青]
created: 2026-05-18
updated: 2026-05-18
sources:
  - "[[Agent Skill]]"
  - "[[Skill-Creator]]"
confidence: high
source_url: https://mp.weixin.qq.com/s/LCpiLyLnRn5WyuHpribyHw
media: article
---

> 系统梳理 Agent Skill 生态三大支柱：Anthropic 的开放 Skill 规范（agentskills.io）与 Skill-Creator 工程化构建方法、Superpowers 的 TDD 式 Writing-Skills 方法论、Google 的 5 种 Skill 设计模式，形成从格式标准到设计模式的完整知识体系。

## 核心要点

- **Skill ≠ Prompt**：Skill 是围绕任务、工具、流程和输出边界的结构化行为设计
- **三层渐进式加载**：L1（name+desc）→ L2（SKILL.md body）→ L3（scripts/references/assets），上下文减少约 90%
- **Skill-Creator**：ML 工程范式移植——训练/测试集分割、A/B 测试、防过拟合、Grader+Comparator+Analyzer 三 Agent 协作
- **Writing-Skills**：TDD 式 RED-GREEN-REFACTOR 循环，压力场景测试纪律型 Skill
- **Google 5 模式**：Tool Wrapper / Generator / Reviewer / Inversion / Pipeline
- **关键陷阱**：description 只写触发条件不写工作流程，否则 Agent 走捷径跳过正文

## 详细笔记

### Agent Skill 规范（agentskills.io）

**SKILL.md 结构**：

```yaml
---
name: skill-name          # 必填，1-64字符，a-z/连字符
description: ...          # 必填，1-1024字符，含触发关键词
license: Apache-2.0       # 可选
metadata:                 # 可选，自定义键值对
  author: example-org
allowed-tools: ...        # 可选，预授权工具
---
# Markdown 指令正文
```

**三层加载机制**：

| 层 | 内容 | 时机 | Token 成本 |
|------|------|------|------------|
| L1 目录层 | name + description | 会话启动 | ~50-100/Skill |
| L2 指令层 | SKILL.md body | 匹配时激活 | <5000 tokens |
| L3 资源层 | scripts/references/assets | 按需加载 | 视文件大小 |

20 个 Skill 初始加载仅 1000-2000 tokens。

### Skill-Creator 六阶段闭环

```
需求捕获 → 编写 Skill → A/B 测试（with/without_skill）
    → Grader 评分 + Comparator 盲比较 + Analyzer 分析
    → 迭代改进 → 优化 Description + 打包 .skill
```

**三个专业化子 Agent**：
- **Grader**：8 步评估流程，含"自我批评"——薄弱断言给 PASS 比无用更糟
- **Comparator**：双盲设计，去偏见化，双维度评分（内容+结构）
- **Analyzer**：事后分析 WHY 赢家赢了 + 基准聚合统计

**已知局限**：Token 消耗极高（20 eval × 3 runs = 60 Opus 会话，单次约 69% 5h 配额）、流程冗长、操作型 Skill 触发率可能为 0%

### Writing-Skills（Superpowers）

TDD 式 RED-GREEN-REFACTOR：
- **RED**：不带 Skill 运行压力场景，记录 Agent 违规+合理化借口
- **GREEN**：针对具体失败编写最小 Skill
- **REFACTOR**：堵住新的合理化借口

四种 Skill 类型：纪律执行型 / 技术指导型 / 思维模式型 / 参考资料型

### Google 5 种设计模式

| 模式 | 核心逻辑 | 适用场景 |
|------|----------|----------|
| Tool Wrapper | 按需加载专家知识 | 框架/库编码规范 |
| Generator | 模板+风格指南强制输出一致 | 标准化文档生成 |
| Reviewer | 检查清单分离，Agent 执行打分 | 自动化 PR 审查 |
| Inversion | Agent 先采访用户再动手 | 需求不明确时 |
| Pipeline | 严格顺序步骤+检查点 | 复杂多步骤任务 |

## 引用与数据

- Agent Skills 规范：[agentskills.io](https://agentskills.io/specification)
- Anthropic 官方 Skills：[github.com/anthropics/skills](https://github.com/anthropics/skills)
- Superpowers：[github.com/obra/superpowers](https://github.com/obra/superpowers)
- Awesome Agent Skills（1060+）：[github.com/VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills)
- 开源 Skill 市场：skills.sh / skillsmp.com / clawhub / alicloud-skills
- 同系列前文：深度解析 OpenClaw、Claude Code、Hermes Agent、LLM Wiki→GBrain

## 相关

- [[Agent Skill]]
- [[Skill-Creator]]
- [[Skill 设计模式（Google 5种）]]
- [[渐进式披露]]
- [[知识工程（Knowledge Engineering）]]
- [[LLM Wiki 模式]]
- [[Wiki 目录]]
