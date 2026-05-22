---
title: 资料摘要：Agent 知识管理与自进化
type: source
tags: [知识工程, 深度, 最佳实践]
created: 2026-05-17
updated: 2026-05-17
sources:
  - "[[知识工程（Knowledge Engineering）]]"
  - "[[LLM Wiki 模式]]"
confidence: high
source_url: https://mp.weixin.qq.com/s/48XpgAMHeaKYj26PrJK-hw
media: article
---

> 阿里云开发者「深度解析」系列第 4 篇，系统梳理 Agent 知识管理从 LLM Wiki 到 GBrain 的技术演进：三层架构、渐进式披露、混合检索、图谱关系，以及 Skillify 作为一种知识组织范式的实践。

## 核心要点

- **LLM Wiki（Karpathy）**：三层架构（raw → wiki → schema），知识被提前"编译"而非每次查询重新检索
- **Obsidian-Wiki**：在 LLM Wiki 基础上增强 — Delta 追踪（SHA-256）、来源可信度边界、溯源标记、hot.md 热缓存
- **GBrain（Garry Tan）**：混合检索（向量粗筛 + 文件精读）、图谱实体关系、Thin Harness Fat Skills 哲学
- **关键机制**：渐进式披露— 先确认相关性，再加载完整知识
- **核心对比**：RAG 是"带着书本进考场"，Skillify 是"把书读透并记成整理后的笔记"
- GBrain Benchmark：带图谱 P@5 = 49.1%，无图谱仅 17.7%（+31.4pp）

## 详细笔记

### 三种方案对比

| 维度 | 传统 RAG | LLM Wiki | GBrain |
|------|----------|----------|--------|
| 知识存储 | 原始文档 | Markdown Wiki | Markdown + 向量索引 |
| 检索方式 | 每次重新搜索 | 读取已编译页面 | 向量过滤 + 文件精读 |
| 交叉引用 | 运行时发现 | 提前建立 | 代码规则 + 反向链接强制 |
| 规模上限 | 理论上无限 | 数百~低千页 | 更大规模 |
| 数据结构 | 无 | wikilink | 节点 + 类型化边 + 可遍历 |
| 响应速度 | 快 | 中 | 中 |

### LLM Wiki 三层架构

```
raw/（不可变源文档）
  ↓ LLM 深度处理
wiki/（LLM 生成的 Markdown 页面集合）
  ↑ 受控于
schema/（定义结构和约定的元指令文件）
```

三个操作闭环：Ingest（摄入）→ Query（查询）→ Lint（巡检）

### Obsidian-Wiki 增强

- **Delta 追踪**：`.manifest.json` + SHA-256 哈希，区分 new/modified/unchanged/deleted
- **来源可信度边界**：源文档被视为不可信，LLM 不执行源中命令
- **溯源标记**：`^[extracted]` / `^[inferred]` / `^[ambiguous]`
- **hot.md**：500 字语义快照，快速恢复上下文
- **Agent 历史摄入**：自动扫描 Claude/Codex/OpenClaw/Hermes 会话历史

### GBrain 架构要点

- **Thin Harness, Fat Skills**：Harness 保持薄，功能通过 Skill 实现
- **潜在空间 vs 确定性**：LLM 决定"做什么"，代码保证"在哪做/怎么做"
- **分层喂给模型**：先"编译真相"（最新摘要），后"时间线证据"（历史来源）
- **图谱 Pipeline**：实体抽取 → 页面生成 → 关系分类 → 反向链接强制化
- **图结构**：节点（实体页）+ 类型化边（works_at/founded/invested_in）+ 图遍历

## 引用与数据

- LLM Wiki 原始 gist：[karpathy/llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- GBrain：[github.com/garrytan/gbrain](https://github.com/garrytan/gbrain)
- Obsidian-Wiki：[github.com/ar9av/obsidian-wiki](https://github.com/ar9av/obsidian-wiki)
- 同系列前文：深度解析 OpenClaw、Claude Code、Hermes Agent

## 相关

- [[知识工程（Knowledge Engineering）]]
- [[渐进式披露]]
- [[LLM Wiki 模式]]
- [[Obsidian-Wiki]]
- [[GBrain]]
- [[AI Workflow]]
- [[MCP（Model Context Protocol）]]
- [[Wiki 目录]]
