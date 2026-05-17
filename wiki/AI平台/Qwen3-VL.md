---
title: Qwen3-VL
type: entity
tags: [VL, 本地部署, 工具]
aliases: [qwen3-vl, Qwen-VL]
created: 2026-05-17
updated: 2026-05-17
sources:
  - "[[资料摘要：本地 VL MCP Vision Server 方案]]"
confidence: medium
---

> 阿里通义千问团队发布的视觉语言模型（VL）系列，支持图像理解和 OCR，在中文 UI 设计稿识别上表现优秀。

## 概述

Qwen3-VL 是 Qwen3 系列的多模态扩展，能同时处理文本和图像输入，输出文字描述。支持多种量化级别（2B–235B MoE），可通过 [Ollama](https://ollama.com/library/qwen3-vl) 在本地运行。许可证为 Apache 2.0，免费商用。

## 关键贡献 / 特性

- 中文 UI 设计稿 OCR 识别优秀（相比 LLaVA 等英文优先模型）
- 多个量化尺寸覆盖从边缘设备到服务器
- Ollama 原生支持（≥ v0.12.7）
- 完全本地运行，零成本，零数据泄露

## 模型规格

| 标签 | 参数量 | 大小 | 适用场景 |
|------|--------|------|----------|
| `qwen3-vl:2b` | ~2B | ~1.5GB | 边缘设备 |
| `qwen3-vl:4b` ⭐ | ~4B | ~2.7GB | **推荐** — 最佳性价比 |
| `qwen3-vl:8b` | ~8.77B | ~5.5GB | 更强能力，需 8GB+ GPU |
| `qwen3-vl:30b` | 31.1B (MoE) | ~20GB | 服务器/生产环境 |
| `qwen3-vl:235b` | 235B (MoE) | — | SOTA 级，需多卡 |

## 与相邻模型的区别

| 模型 | 区别 |
|------|------|
| LLaVA | LLaVA 也是开源 VL，但中文 UI 识别远逊于 Qwen3-VL |
| GPT-4V | 商业闭源 + API 调用，Qwen3-VL 免费本地运行 |
| Qwen3（纯文本） | 无视觉能力 |

## 已知限制

- 需要 Ollama ≥ v0.12.7，旧版 Ollama 不兼容

## 相关

- [[Ollama]]
- [[MCP Vision Server 方案]]
- [[MCP（Model Context Protocol）]]
- [[Wiki 目录]]
