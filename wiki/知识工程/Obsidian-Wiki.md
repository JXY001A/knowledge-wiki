---
title: Obsidian-Wiki
type: entity
tags: [知识工程, 工具]
aliases: [obsidian-wiki]
created: 2026-05-17
updated: 2026-05-17
sources:
  - "[[资料摘要：Agent 知识管理与自进化]]"
confidence: medium
---

> 基于 Skill 的多 Agent 框架，实现 Karpathy 的 LLM Wiki 模式，支持 9+ 种 Agent、Delta 追踪、来源可信度边界和 Agent 历史自动摄入。

## 概述

Obsidian-Wiki 是 LLM Wiki 的工程化实现，核心理念：Agent 无关、Skill 驱动、Obsidian 原生。利用 Obsidian 的 wikilink、图谱视图和 Dataview 等功能管理知识。

## 关键贡献 / 特性

- **Delta 追踪**：`.manifest.json` + SHA-256 哈希追踪所有来源，区分 new/modified/unchanged/deleted
- **来源可信度边界**：源文档不可信，LLM 不执行源中命令（防 prompt injection）
- **溯源标记**：`^[extracted]` / `^[inferred]` / `^[ambiguous]`
- **hot.md 热缓存**：500 字语义快照，快速恢复上下文
- **Agent 历史摄入**：自动扫描 Claude/Codex/OpenClaw/Hermes 会话历史
- **知识图谱 Skills**：cross-linker（置信度评分连接）、graph-colorize（可视化着色）
- 20+ 标准化 Skill 文件

## 与 LLM Wiki 的差异

| LLM Wiki | Obsidian-Wiki |
|----------|---------------|
| 纯思想文章 | 工程化实现 |
| 单一 Agent | 9+ Agent 兼容 |
| 手动触发 | Agent 历史自动摄入 |
| 无差异追踪 | SHA-256 Delta 追踪 |

## 相关

- [[LLM Wiki 模式]]
- [[GBrain]]
- [[知识工程（Knowledge Engineering）]]
- [[Wiki 目录]]
