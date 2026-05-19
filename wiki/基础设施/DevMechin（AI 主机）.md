---
title: DevMechin（AI 主机）
type: entity
tags: [基础设施, 本地部署]
aliases: [DevMechin, AI主机, Ubuntu主机]
created: 2026-05-19
updated: 2026-05-19
sources: []
confidence: high
---

> 个人 AI 推理服务器，运行 Ubuntu 24.04，搭载 RTX 4080 SUPER，用于本地部署 Ollama、Jupyter 等服务。

## 硬件规格

| 组件 | 型号 | 详情 |
|------|------|------|
| **CPU** | Intel Core i7-14700KF | 20 核，最高 5.6GHz |
| **GPU** | NVIDIA GeForce RTX 4080 SUPER | 16GB GDDR6X，CUDA 12.4，驱动 550.120 |
| **内存** | 32GB DDR5 | 可用约 28GB |
| **磁盘** | NVMe SSD 306GB | 已用 47G，剩余 242G |
| **主板** | Gigabyte Z790M AORUS ELITE AX ICE | — |
| **系统** | Ubuntu 24.04.2 LTS | Kernel 6.11.0-21-generic |

## 连接方式

### 内网（从 Mac 连接）

```bash
ssh jxy001a1@192.168.71.127
```

已配置 SSH 密钥免密登录（`~/.ssh/id_ed25519`）。sudo 密码已通过安全渠道保存。

### 公网（通过阿里云穿透）

```
8.133.175.201  ← 阿里云轻量（上海）
     ↑ frp 隧道
192.168.71.127 ← DevMechin 本机
```

| 服务 | 本地端口 | 公网端口 | 访问方式 |
|------|----------|----------|----------|
| SSH | 22 | — | 内网直连 |
| Jupyter | 8888 | 8888 | `http://8.133.175.201:8888` |
| Ollama API | 11434 | 11434 | `http://8.133.175.201:11434` |

## 运行的服务

| 服务 | 管理方式 | 开机自启 |
|------|----------|----------|
| `frpc`（隧道客户端） | `systemctl --user start/stop frpc` | ✅ |
| `ollama`（模型推理） | `sudo systemctl start/stop ollama` | ✅ |
| Jupyter | 手动 `jupyter lab` | ❌ |

## 维护命令

```bash
# 查看 frpc 状态
systemctl --user status frpc

# 查看 Ollama 状态
sudo systemctl status ollama

# 查看 GPU 状态
nvidia-smi

# 查看已安装模型
ollama list

# 拉取模型
ollama pull <model-name>
```

## 相关

- [[RGB 灯带控制]]
- [[Ollama]]
- [[MCP Vision Server 方案]]
- [[Wiki 目录]]
