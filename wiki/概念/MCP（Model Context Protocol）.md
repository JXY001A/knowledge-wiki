---
title: MCP（Model Context Protocol）
type: concept
tags: [概念, MCP, 进阶]
aliases: [MCP, Model Context Protocol, MCP协议]
created: 2026-05-16
updated: 2026-05-16
sources:
  - "[[资料摘要：本地 VL MCP Vision Server 方案]]"
related_concepts: []
confidence: medium
---

> MCP（Model Context Protocol）是 Anthropic 发布的开放协议，定义 AI 应用与外部工具/数据源之间的标准通信接口，采用 JSON-RPC over stdio/HTTP 传输。

## 是什么

MCP 是一种 Client-Server 协议，AI 宿主（如 Claude Code）作为 Client，外部工具/服务作为 Server。Server 暴露 `list_tools()` 声明能力，Client 调用 `call_tool()` 执行。传输层支持 stdio（本地进程）和 HTTP（远程服务）。

## 为什么重要

它解决了 AI 模型与外部世界交互的标准化问题。在 MCP 之前，每个 AI 工具都有独立的集成方式；MCP 提供了一个统一接口，使得一次开发的工具可被所有兼容 Client 使用。

## 工作原理

```
┌──────────────┐    MCP (JSON-RPC)    ┌──────────────┐
│  Host (Claude │◄──────────────────►│  MCP Server   │
│  Code 等)     │  stdio / HTTP       │  (自定义工具)  │
└──────────────┘                      └──────┬────────┘
                                              │
                                              ▼
                                      ┌──────────────┐
                                      │  后端服务     │
                                      │  (API/DB 等) │
                                      └──────────────┘
```

核心概念：
- **Tools**：Server 暴露的可调用函数，带 inputSchema
- **Resources**：Server 暴露的数据资源
- **Prompts**：Server 预定义的 Prompt 模板

## 历史与演进

Anthropic 于 2024 年 11 月发布 MCP，旨在成为 AI 工具互操作的开放标准。随后多个 IDE（Cursor、Codex、Gemini CLI 等）支持 MCP。Claude Code 通过 `.mcp.json` + `settings.local.json` 注册 MCP Server。

## 常见误解

- **MCP = HTTP API** — MCP 是协议层，定义了工具发现和调用的语义，不同于原始 HTTP API
- **MCP 只能本地** — stdio 适合本地，但 MCP 也支持 HTTP transport 用于远程 Server

## 与相邻概念的区别

| 概念 | 区别 |
|------|------|
| Function Calling | FC 是 LLM 内在能力，MCP 是进程间协议，两者互补 |
| LangChain Tools | LangChain 是 Python 框架内的抽象，MCP 是跨语言/跨进程的标准协议 |
| REST API | REST 是通用 HTTP 接口，MCP 定义了 AI 专用的 Tool/Resource/Prompt 语义 |

## 相关

- [[MCP Vision Server 方案]]
- [[Ollama]]
- [[AI Workflow]]
- [[Wiki 目录]]
