---
title: Ollama
type: entity
tags: [工具, LLM, 本地部署]
aliases: [ollama]
created: 2026-05-16
updated: 2026-05-16
sources:
  - "[[资料摘要：本地 VL MCP Vision Server 方案]]"
confidence: high
---

> Ollama 是一个本地运行大语言模型（LLM）和视觉语言模型（VL）的开源工具，支持 macOS/Linux/Windows，一行命令即可拉取并运行模型。

## 概述

Ollama 将模型的下载、量化、GPU 推理和 API 服务封装为单一二进制，提供与 OpenAI 兼容的 HTTP API（默认 `localhost:11434`）。支持 CPU-only 和 Apple Silicon GPU 推理。官方模型库托管于 [ollama.com/library](https://ollama.com/library)。

## 关键贡献 / 特性

- 一键运行模型：`ollama run qwen3-vl:4b`
- Apple Silicon GPU 加速（Metal）
- 兼容 OpenAI API 格式
- 支持 GGUF 量化模型
- 本地数据不出机器

## 常用命令

```bash
ollama pull <model>     # 拉取模型
ollama run <model>      # 交互式运行
ollama serve             # 启动 API 服务
ollama list              # 列出已安装模型
```

## 安装

```bash
brew install --formula ollama
brew services start ollama
```

## 已知限制

- Qwen3-VL 系列需要 Ollama ≥ v0.12.7
- 旧版（< v0.12）不兼容较新的 VL 模型
- 默认监听 `127.0.0.1:11434`（仅本地）

## 相关

- [[MCP Vision Server 方案]]
- [[MCP（Model Context Protocol）]]
- [[资料摘要：本地 VL MCP Vision Server 方案]]
- [[DeepSeek]]
- [[Wiki 目录]]
