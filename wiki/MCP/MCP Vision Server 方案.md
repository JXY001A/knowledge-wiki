---
title: MCP Vision Server 方案
type: entity
tags: [MCP, VL, 工具]
aliases: [vision-server, Vision MCP]
created: 2026-05-16
updated: 2026-05-16
sources:
  - "[[资料摘要：本地 VL MCP Vision Server 方案]]"
confidence: high
---

> 通过 MCP 协议将本地视觉语言模型（Ollama + Qwen3-VL/LLaVA）接入 Claude Code，使纯文本模型具备"看懂设计稿"的能力。

## 概述

Claude Code 使用 DeepSeek V4 Pro 纯文本模型时不支持多模态。MCP Vision Server 在中间架桥：接收设计稿图片路径 → base64 编码 → 调 Ollama 本地 VL 模型 → 返回结构化 UI 描述 → Claude Code 据此生成代码。

## 关键贡献 / 特性

- 零成本方案：全部使用开源免费组件
- MCP stdio 协议，标准 Claude Code 集成
- 8 维度 Prompt 工程（布局、导航、内容、文案、配色、间距、交互、细节）
- 支持模型热切换（Qwen3-VL ⇄ LLaVA）
- ~90 行 Python，轻量可维护

## 技术栈

| 层 | 组件 |
|------|------|
| AI 模型 | Qwen3-VL:4b（首选）/ LLaVA:7b（备选） |
| 推理服务 | Ollama（localhost:11434） |
| 协议 | MCP（stdio transport） |
| Server | Python（`mcp` + `httpx`） |
| 集成 | `.mcp.json` + `settings.local.json` |

## 当前状态

- Ollama v0.7.0 已安装，需升级到 v0.12.7+
- LLaVA:7b 链路已跑通（降级方案）
- 待拉取 Qwen3-VL:4b 并切换

## 相关

- [[资料摘要：本地 VL MCP Vision Server 方案]]
- [[Ollama]]
- [[MCP（Model Context Protocol）]]
- [[DeepSeek]]
- [[Wiki 目录]]
