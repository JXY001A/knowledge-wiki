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
                                   ├─ wiki-mcp-server   ← MCP 协议，frp 暴露 :9300
                                   ├─ wecom-bot-webhook ← 企业微信回调，frp 暴露 :9400
                                   ├─ Ollama（qwen3-vl:8b） ← 图片解析
                                   └─ embedding 模型 ← 语义搜索（后期）

外部 AI 工具 ──MCP──> 8.133.175.201:9300 ──frp──> DevMechin wiki-mcp-server
手机微信 ──企业微信 Bot──> 8.133.175.201:9400 ──frp──> DevMechin wecom-bot-webhook

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

[[proxies]]
name = "wecom-webhook"
type = "tcp"
localIP = "127.0.0.1"
localPort = 9400
remotePort = 9400
```

外部访问方式：
- MCP Server：`http://8.133.175.201:9300`
- 企业微信 Bot webhook：`http://8.133.175.201:9400/webhook`

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

### 移动端提交：企业微信 Bot

手机端通过企业微信 Bot 提交知识，数据流：

```
手机微信 ──发消息──> 企业微信 Bot ──POST 回调──> 8.133.175.201:9400/webhook
                                                    ──frp──>
DevMechin wecom-bot-webhook（Flask/FastAPI）
  ↓
调用 wiki-mcp-server ingest（本地 localhost:9300）
  ↓
git push → GitHub
```

**为什么选企业微信 Bot：**
- 微信内直接使用，不装额外 App
- 企业微信免费注册，Bot API 官方支持，无封号风险
- 可以只加自己一个人
- 支持文字/图片/链接，覆盖绝大多数移动端提交场景

**消息类型处理：**

| 消息类型 | 用户操作 | Bot 处理 |
|----------|----------|----------|
| 文本链接 | 粘贴 URL | `defuddle` 清洗 → `raw/` → ingest |
| 文字内容 | 打一段想法 | 保存为 `raw/收件箱/` → ingest |
| 截图/图片 | 手机截图发送 | `vision` 脚本（qwen3-vl:8b）解析 → ingest |
| 转发文章 | 转发公众号文章 | 提取原文链接 → defuddle → ingest |

**wecom-bot-webhook 实现要点：**
- Flask/FastAPI 单文件，~150 行
- 验证企业微信签名（安全）
- 收到消息后异步调用 wiki-mcp ingest，完成后回复处理结果
- systemd 托管，随 frpc 开机自启

**其他移动端方案备选：**

| 方案 | 推荐度 | 理由 |
|------|--------|------|
| 企业微信 Bot | ⭐⭐⭐ | 微信原生体验，官方 API，免费 |
| GitHub Issues | ⭐⭐ | 零开发，但体验不如聊天式提交 |
| Obsidian Mobile | ⭐ | 只能纯 markdown 编辑，无 AI 处理 |
| Telegram Bot | ⭐⭐ | 体验好但需额外注册 + 翻墙 |
| 微信小程序 | ❌ | 一个人用投入产出不成比例 |

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
2. ~~本地 `~/bin/vision` 图片解析脚本~~ ✅ 已完成
3. ~~DevMechin 上 clone 仓库~~ ✅ 已完成（`~/code/knowledge-wiki`）
4. ~~编写 wiki-mcp-server（ingest / query / lint / search）~~ ✅ 已完成（FastMCP + Streamable HTTP）
5. ~~编写 wecom-bot-webhook（~150 行 Flask）~~ ✅ 已完成（Flask，含企微加解密）
6. ~~frpc.toml 新增 9300 + 9400 端口映射~~ ✅ 已完成
7. ~~配置 systemd 服务（wiki-mcp + wecom-webhook，开机自启）~~ ✅ 已完成
8. ~~注册企业微信，配置 Bot 回调 URL~~ ✅ 已完成
9. ~~配置 Mac 本地 Claude Code → MCP Client~~ ✅ 已完成（`.mcp.json` + `~/.claude/mcp.json`）

## 开放问题

- 语义搜索层何时引入？（建议 wiki 超过 100 页后再评估）
- MCP Server 协议选择：stdio 模式（适合本地调用）还是 streamable HTTP（适合远程调用）？外网穿透场景建议 HTTP
- 是否需要认证层？当前未加，依赖 GitHub 私有仓库 + frp 隐式安全。企业微信 Bot 自带签名验证

## 相关

- [[DevMechin（AI 主机）]]
- [[MCP Vision Server 方案]]
- [[LLM Wiki 模式]]
- [[RGB 灯带控制]]
- [[Wiki 目录]]
