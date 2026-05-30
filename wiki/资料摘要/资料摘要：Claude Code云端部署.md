---
title: 资料摘要：Claude Code云端部署
type: source
tags: ["教程", "部署", "沙箱", "智能体", "最佳实践"]
created: 2026-05-30
updated: 2026-05-30
sources: []
confidence: medium
source_url: https://mp.weixin.qq.com/s/gaBKZFIZetj9H9eqyhT13g
media: article
---

> 本文详述将Claude Code从本地CLI工具改造为云端HTTP流式服务的方案。通过npm pack离线打包解决无外网安装问题，基于claude-agent-sdk+FastAPI+SSE实现流式HTTP API，支持单次查询/多轮会话及Hooks、Subagents、MCP等高级特性。采用一用户一沙箱+文件版本化存储架构实现多用户隔离，沙箱实例无状态、可回收复用，用户记忆与配置持久化于对象存储。方案坚持“外层封装、不改造核心”原则，升级成本低，不到2人日耗时完成。

## 核心要点

- 使用npm pack生成离线tgz包，在无外网服务器安装Claude Code CLI，并搭配离线Node.js环境
- 基于claude-agent-sdk+FastAPI+SSE将CLI转为HTTP流式服务，支持单次查询与多轮会话
- 沙箱隔离采用“一用户一沙箱”+文件版本化（~/.claude/等目录）持久化到OSS，实例无状态
- HTTP服务完整支持权限控制、子代理、MCP服务器、生命周期钩子等高级特性
- 沙箱生命周期支持按需分配、闲置回收与主动释放，资源弹性伸缩
- 外层封装不改造Claude Code本体，仅需更新基础镜像即可升级，维护成本低

## 详细笔记

## 背景与问题
Harness Engineering理念提出后，Agent设计要求更高，自行开发ReactAgent需补充约束层、评估机制、子Agent等。最快路径是部署现有产品（如Claude Code）并在其上进行封装。

三个核心问题：
1. 离线部署：部分服务器无外网，不支持在线安装
2. 服务化输出：CLI非流式，输出终端图形界面，不可供程序消费
3. 多用户隔离：Claude Code单实例，记忆与配置以文件持久化，容易串扰

## 方案总览
四层架构：
- 第一层：云端离线部署（npm pack + 离线安装）
- 第二层：HTTP流式服务化（FastAPI + SSE 封装 claude-agent-sdk）
- 第三层：Docker基础镜像构建
- 第四层：沙箱多实例隔离（一用户一沙箱 + 用户文件版本化存储）

## 离线部署细节
- 环境要求：Node.js 18+，确认CPU架构
- 获取离线包：`npm pack @anthropic-ai/claude-code` 生成 `.tgz` 文件，或整目录打包
- 离线安装：上传tgz，`sudo npm install -g ./包名.tgz`
- 注意事项：CPU架构匹配；npm pack不含依赖，必要时用整目录打包；运行时仍需网络访问Anthropic API，需配置内网代理

## HTTP服务化（基于FastAPI重写SDK）
技术栈：FastAPI + sse-starlette + claude-agent-sdk + Pydantic

### 项目结构
- `app/models/schemas.py`：Pydantic模型
- `app/services/agent_service.py`：SDK封装，消息序列化为SSE事件
- `app/routers/query.py`：单次查询（同步/SSE流式）
- `app/routers/sessions.py`：多轮会话管理

### 核心设计
- `query()` 异步迭代器产出的消息（SystemMessage、AssistantMessage、ResultMessage）被序列化为JSON，通过SSE推送
- 流式端点 `/v1/query/stream` 返回 `text/event-stream`，客户端可实时接收文本、工具调用等事件
- 多轮会话基于 `StreamingSession`，内部维护消息队列和响应队列，通过后台循环驱动 `ClaudeSDKClient`，支持心跳保活与超时处理

### 高级功能
- 权限模式：支持 default/dontAsk/acceptEdits/bypassPermissions/plan，默认 bypassPermissions 避免无人值守阻塞
- 子代理：通过API定义专用子代理并指定工具集、模型和提示词
- MCP集成：支持连接外部MCP服务器（stdio/http/sse）
- 钩子：PreToolUse/PostToolUse生命周期钩子，用于审计、拦截等

### 踩坑记录
- SDK版本问题：文档引用的版本不存在，改为 `>=0.1.60`
- 权限拦截问题：默认权限模式导致读取配置文件卡死，通过默认 bypassPermissions 解决
- 闭包变量绑定：动态生成钩子函数时循环变量延迟绑定，用默认参数捕获修复
- 异步阻塞：SDK部分同步函数需通过 `asyncio.to_thread()` 包装

## 基础镜像构建
Dockerfile 分阶段：引入沙箱基础层、安装系统依赖+Node.js+Python 3.11、安装Claude Code CLI、部署HTTP服务。容器启动脚本仅拉起 `python3 run.py` 监听8765端口。

## 沙箱隔离与文件版本化存储
### 问题本质
Claude Code 是单用户本地文件系统状态，若共享实例会导致记忆串扰、配置冲突、文件污染、会话冲突。

### 核心思路
一用户一沙箱（容器级隔离）+ 用户文件版本化存储。用户所有状态文件（`~/.claude/`、`~/workspace/` 等）视为“文件快照”持久化到OSS/NAS。

### 流程
1. 用户请求到达控制平面，查找活跃沙箱
2. 若无活跃沙箱，分配空闲实例，从存储拉取该用户最新文件快照
3. 启动HTTP服务，转发请求
4. 闲置超时或主动销毁时，对比文件增量差异，上传变更，记录新版本
5. 释放实例回池

### 数据模型
`user_snapshots` 表记录 `user_id`、`version`、`storage_key`、时间戳等。

### 优势
彻底隔离；状态永不丢失；资源弹性伸缩；天然版本回溯，为误操作提供恢复能力。

## 总结
方案耗时：1.5人日 + 1909 Credits。设计原则：外层封装，不修改Claude Code本体，升级成本低。个人感悟强调AI提效依赖工程师的设计能力。

## 引用与数据

尽量不改造 Claude Code 本身，而是在外围做封装和调度。
从 claude code部署调研->部署方案设计->重构sdk为FastApi项目->基础镜像构建->沙箱部署->本篇ata撰写 仅仅耗时1.5人日及1909 Credits
个人的工程设计能力 始终是借助ai高效产出的基础，合理的设计思路才能快速引导Ai构建高质量系统

## 相关

- [[Harness Engineering]]
- [[claude-agent-sdk]]
- [[SSE流式推送]]
- [[沙箱多实例隔离]]
- [[用户文件版本化存储]]
- [[Claude Code]]
- [[claude-agent-sdk]]
- [[FastAPI SSE流式]]
- [[沙箱隔离]]
- [[MCP集成]]

- [[Wiki 目录]]
