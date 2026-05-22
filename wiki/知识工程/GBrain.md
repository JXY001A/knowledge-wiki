---
title: GBrain
type: entity
tags: [知识工程, 工具, 图谱]
aliases: [gbrain]
created: 2026-05-17
updated: 2026-05-17
sources:
  - "[[资料摘要：Agent 知识管理与自进化]]"
confidence: medium
---

> Y Combinator 总裁 Garry Tan 构建的知识库项目，在 LLM Wiki 的极简哲学基础上引入混合检索和图谱实体关系，解决规模化瓶颈。

## 概述

GBrain 的架构哲学：**Thin Harness, Fat Skills**——Harness 保持薄，功能通过 Skill 实现。核心理念：让 LLM 决定"做什么"（潜在空间），让代码保证"在哪做/怎么做"（确定性）。

## 关键贡献 / 特性

### 混合检索架构

```
Chunk 确认（向量粗筛 ~2KB）
    ↓
整页加载（get_page() 完整 Markdown）
    ↓
分层呈现（先结论 → 后证据）
```

不是 RAG 的"搜索即召回"，而是"向量过滤 + 文件精读"的折衷方案。

### 图谱实体关系

| 组件 | 实现 |
|------|------|
| 节点 | 每个实体页面（people/、companies/） |
| 边 | `(Source, Relation_Type, Target)` 存储在 links 表 |
| 关系类型 | works_at、founded、invested_in、advises 等 |
| 图遍历 | `graph-query <slug> --depth N` |

### Benchmark 数据

| 指标 | 带图谱 | 无图谱 | 差距 |
|------|--------|--------|------|
| P@5 | 49.1% | 17.7% | +31.4 pp |

back-link boost 是主要提升来源。

### 多模态支持

支持视频、音频、PDF、截图等多模态内容，通过自动转录、OCR 和实体抽取转化为结构化信息。

## 与 LLM Wiki 的差异

| LLM Wiki | GBrain |
|----------|--------|
| 纯 Markdown | Markdown + 向量索引 + 图结构 |
| wikilink | 类型化边 + 可遍历图 |
| 数百页上限 | 更大规模 |
| grep/index.md 搜索 | 混合搜索（BM25 + 向量） |

## 相关

- [[LLM Wiki 模式]]
- [[Obsidian-Wiki]]
- [[渐进式披露]]
- [[知识工程（Knowledge Engineering）]]
- [[Wiki 目录]]
