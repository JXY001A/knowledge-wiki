---
title: 渐进式披露（Progressive Disclosure）
type: concept
tags: [概念, 知识工程, 基础]
aliases: [Progressive Disclosure, 渐进式加载]
created: 2026-05-17
updated: 2026-05-17
sources:
  - "[[资料摘要：Agent 知识管理与自进化]]"
related_concepts: [[知识工程（Knowledge Engineering）]]
confidence: high
---

> 渐进式披露是一种知识加载策略：先以低成本方式确认信息相关性，确认后再加载完整内容，避免无效的大上下文填充。

## 是什么

渐进式披露的核心逻辑是"先切片后全量"：用轻量手段（如向量检索、索引扫描、标题匹配）先筛选出候选集，确认相关性后再加载完整页面内容。它不是一次性把所有相关信息塞进 Context Window，而是按优先级分层呈现——先结论，后证据。

## 为什么重要

Context Window 虽然越来越大，但无效信息填充仍会稀释模型注意力，增加 Token 消耗。渐进式披露在保证答案质量的同时，最小化上下文成本。在 GBrain 的实现中，这种策略使 P@5 从 17.7% 提升到 49.1%。

## 工作原理

```
查询到达
    ↓
第一层：低成本确认（向量粗筛 / index.md 扫描）
    ↓ 确认相关
第二层：加载完整页面
    ↓
第三层：分层呈现（先"编译真相"→ 后"时间线证据"）
```

## 与相邻概念的区别

| 概念 | 区别 |
|------|------|
| RAG | RAG 直接拼接召回片段，渐进式披露先确认再加载完整页 |
| Context Window 最大化 | 堆满上下文 vs 按需分层加载 |
| Tool Calling | Tool Calling 是执行能力，渐进式披露是知识加载策略 |

## 相关

- [[LLM Wiki 模式]]
- [[GBrain]]
- [[知识工程（Knowledge Engineering）]]
- [[Wiki 目录]]
