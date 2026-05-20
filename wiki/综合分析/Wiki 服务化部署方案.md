---
title: Wiki 服务化部署方案
type: synthesis
tags: [基础设施, 服务部署, MCP, 知识工程]
created: 2026-05-20
updated: 2026-05-20
sources:
  - "[[DevMechin（AI 主机）]]"
  - "[[MCP Vision Server 方案]]"
  - "[[LLM Wiki 模式]]"
confidence: high
---

> 将 knowledge-wiki 从本地 Obsidian vault 升级为可被外部 AI 工具通过 API 访问的个人知识库服务。核心思路：git 是存储层，MCP 是接口层，Obsidian 是人类 UI 层。

## 架构总览

```
                           GitHub（JXY001A/knowledge-wiki）
                           ↑       ↑
                     git pull   git push
                           |       |
Mac（Obsidian + Claude Code）     DevMechin（服务端，192.168.71.127）
                                  ├─ wiki-mcp-server  ← MCP 协议，frp 暴露 :9300
                                  ├─ Ollama（qwen3-vl:8b） ← 图片解析
                                  └─ embedding 模型 ← 语义搜索（后期）

外部 AI 工具 ──MCP──> 8.133.175.201:9300 ──frp──> DevMechin wiki-mcp-server
```

## 组件清单

### 存储层：GitHub 私有仓库

- 仓库：`git@github.com:JXY001A/knowledge-wiki.git`
- 已建立，Mac 本地已关联 remote
- Mac 和 DevMechin 各持一份 clone，通过 GitHub 同步

### 接口层：wiki-mcp-server

部署在 DevMechin，对外暴露 MCP 协议。提供 4 个工具：

| 工具 | 输入 | 行为 |
|------|------|------|
| `ingest` | 文件路径 或 URL | git pull → 按 Schema 生成/更新页面 → git push |
| `query` | 自然语言问题 | git pull → 读 wiki 页面 → 综合回答（附 wikilink 引用） |
| `lint` | — | git pull → 巡检（孤页/死链/过时/矛盾/标签规范）→ 输出报告 |
| `search` | 关键词 | grep wiki/ → 返回匹配页面列表 |

接入协议为标准 MCP（streamable HTTP 或 stdio），任何支持 MCP 的 AI 工具均可接入。

### 穿透层：frp 隧道

在 DevMechin 上 `frpc.toml` 新增端口映射：

```toml
[[proxies]]
name = "wiki-mcp"
type = "tcp"
localIP = "127.0.0.1"
localPort = 9300
remotePort = 9300
```

外部 AI 工具通过 `http://8.133.175.201:9300` 访问 MCP Server。

### 服务管理：systemd

```ini
# ~/.config/systemd/user/wiki-mcp.service
[Unit]
Description=Wiki MCP Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/jxy001a1/code/wiki-mcp-server/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

systemd 托管，随 frpc 一起开机自启。

## 同步机制

### 核心策略：操作前 pull + 写后 push

```
MCP ingest 请求到达
  ↓
git pull --rebase          ← 拉取 Mac 端可能的新提交
  ↓
写入 wiki 文件、更新目录
  ↓
git add -A && git commit && git push   ← 推送变更
```

### 为什么无需额外触发机制

- **冲突窗口极小** —— 个人使用，Mac 人类编辑和 MCP 调用几乎不会同时发生
- **git pull --rebase 可自动合并** —— wiki 页面是纯文本 markdown，合并成功率极高
- **零额外组件** —— 不依赖 webhook、消息队列、定时任务
- **延迟可忽略** —— 内网 git pull 1-2 秒

### 冲突处理

如果 Mac 上 Obsidian 编辑了某页面且未 push，同时 MCP 也修改了同一页，rebase 可能冲突。缓解措施：

1. MCP 操作限制领域：只写 ingest 新建页面、目录、操作日志，不触碰人类直接编辑的内容页
2. 约定：人类编辑完后及时 `git push`，MCP 操作前先 pull，天然串行化

## 图片解析

MCP Server 不直接处理图片。图片解析走独立的 `~/bin/vision` 脚本，通过 DevMechin Ollama API（`192.168.71.127:11434`）调用 `qwen3-vl:8b`：

```bash
~/bin/vision /path/to/screenshot.png
```

相比之前的 MCP Vision Server（JSON-RPC over stdio → DashScope/Ollama），直接 HTTP API 调用省掉了 MCP 协议层开销。

若需速度优先，可在 DevMechin 上 `ollama pull qwen3-vl:2b`，预计 10 秒内出结果。

## 实施步骤

1. ~~GitHub 私有仓库~~ ✅ 已完成
2. DevMechin 上 clone 仓库
3. 编写 wiki-mcp-server（ingest / query / lint / search）
4. frpc.toml 新增 9300 端口映射
5. 配置 systemd 服务（开机自启）
6. 端到端测试：Mac 上 Claude Code → MCP → 8.133.175.201:9300 → DevMechin

## 开放问题

- 语义搜索层何时引入？（建议 wiki 超过 100 页后再评估）
- MCP Server 协议选择：stdio 模式（适合本地调用）还是 streamable HTTP（适合远程调用）？外网穿透场景建议 HTTP
- 是否需要认证层？当前未加，依赖 GitHub 私有仓库 + frp 隐式安全

## 相关

- [[DevMechin（AI 主机）]]
- [[MCP Vision Server 方案]]
- [[LLM Wiki 模式]]
- [[Wiki 目录]]
