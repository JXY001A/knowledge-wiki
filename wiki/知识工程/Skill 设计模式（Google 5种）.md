---
title: Skill 设计模式（Google 5种）
type: topic
tags: [知识工程, 设计模式, 最佳实践]
aliases: [Google Skill 设计模式, 5种Skill设计模式]
created: 2026-05-18
updated: 2026-05-18
sources:
  - "[[资料摘要：Agent Skill 规范构建与设计模式]]"
confidence: medium
---

> Google ADK 团队从生态中总结的 5 种 Agent Skill 内部设计模式，解决"SKILL.md 格式一样但内部逻辑该怎么设计"的问题。

## 五种模式总览

| 模式 | 核心逻辑 | 一句话 |
|------|----------|--------|
| **Tool Wrapper** | 按需加载专家知识 | "给你装个技能包，用到时才加载" |
| **Generator** | 模板+风格指南强制输出一致 | "填空题文档生成" |
| **Reviewer** | 检查清单分离，Agent 执行打分 | "查什么和怎么查分开" |
| **Inversion** | Agent 先采访用户再动手 | "先问清楚再干活" |
| **Pipeline** | 严格顺序步骤+检查点 | "不跳步的多环节流水线" |

## 详细对比

### Tool Wrapper

```markdown
## 审查代码时
1. 加载规范参考文件
2. 对照每条规范逐一检查用户代码
3. 针对每处违规，引用具体规则并给出修改建议
```

关键：SKILL.md 本身不包含完整规范，告诉 Agent 去哪里加载什么。

### Generator

```markdown
第三步：向用户询问缺失信息：主题、关键发现、目标受众
```

关键：缺什么直接问，不瞎猜。

### Reviewer

```markdown
针对每处违规：
- 记录行号
- 划分严重等级：错误/警告/提示
- 解释问题的原因（WHY），而不仅仅是描述问题（WHAT）
```

关键：检查清单独立维护，Agent 专注打分+"WHY not WHAT"。

### Inversion

```markdown
## 第一阶段 — 问题探索（每次只提一个问题）
问题1："这个项目解决什么问题？"
问题2："主要用户群体是哪些？"
...
在所有阶段完成之前，请勿开始构建。
```

关键：翻转交互——Agent 先采访收集完整需求。

### Pipeline

```markdown
## 第二步 — 生成文档字符串
在用户确认之前，不得进入第三步。
```

关键：每步有硬性检查点，用户不点头 Agent 不往下。

## 如何选择

| 需求 | 模式 |
|------|------|
| 特定技术栈专家知识 | Tool Wrapper |
| 一致的结构化输出 | Generator |
| 自动化代码/内容审查 | Reviewer |
| 需求不明确 | Inversion |
| 复杂多步骤任务 | Pipeline |
| 不确定？ | 从 Tool Wrapper 开始 |

## 组合推荐

| 组合 | 场景 |
|------|------|
| Pipeline + Reviewer | 文档生成后自动质量检查 |
| Generator + Inversion | 先收集信息再填充模板 |
| Pipeline + Tool Wrapper | 多步骤代码生成 |
| Inversion + Pipeline | 复杂项目全流程 |

## 相关

- [[Agent Skill]]
- [[Skill-Creator]]
- [[渐进式披露（Progressive Disclosure）]]
- [[知识工程（Knowledge Engineering）]]
- [[Wiki 目录]]
