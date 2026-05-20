---
title: 资料摘要：OpenClaw 多平台适配器架构
type: source
tags: [工具, MCP, 服务部署]
created: 2026-05-20
updated: 2026-05-20
sources: []
confidence: high
source_url: https://github.com/openclaw/openclaw
media: code
---

> OpenClaw 通过 ChannelPlugin 适配器模式统一接入 25+ 个即时通讯平台，是研究“一对多消息集成”的标准参考实现。

## 核心要点

- 一个 `ChannelPlugin` TypeScript 接口，35+ 个可选适配器，每个平台只实现自己需要的子集
- 消息标准化：所有平台的消息格式转换为统一的内部 `MessageEvent`
- 会话隔离：`platform:chat_id:user_id` 组合键
- 扩展目录结构：`extensions/<平台名>/` 下独立包，惰性加载

## 适配器接口设计

```typescript
type ChannelPlugin = {
  id: ChannelId;           // "telegram" | "qqbot" | "dingtalk" | ...
  meta: ChannelMeta;       // 名称、图标、标签
  capabilities: ChannelCapabilities; // chatTypes, media, streaming 等

  // 35+ 个可选适配器，每个平台选实现：
  config?: ChannelConfigAdapter;     // 配置项读写
  setup?: ChannelSetupAdapter;       // 初始化（扫码/授权）
  messaging?: ChannelMessagingAdapter; // 消息收发
  gateway?: ChannelGatewayAdapter;   // HTTP/WS 连接管理
  security?: ChannelSecurityAdapter;  // 加解密、签名验证
  streaming?: ChannelStreamingAdapter; // 流式回复
  pairing?: ChannelPairingAdapter;   // 设备扫码配对
  outbound?: ChannelOutboundAdapter; // 主动外呼
  groups?: ChannelGroupAdapter;      // 群组管理
  // ... 还有 25+ 个
};
```

**设计精髓：** 接口用组合（composition）而非继承——每个适配器是一个独立的小 slice，平台按需组装。新增平台 = 实现一个 `ChannelPlugin` 对象，不触碰核心代码。

## 关键平台实现要点

### Telegram（最简单的参考）

- 接入方式：Bot Token + Webhook 或长轮询
- 核心适配器：`messaging`（接收 update）、`streaming`（流式发送）、`security`（HMAC 验证）
- Webhook 部署：`http://<host>/telegram/webhook/<token>`

### 企业微信 / QQ Bot

- 接入方式：AppID + ClientSecret + WebSocket 或 Webhook
- 核心适配器：`security`（签名验证 + AES 加解密）、`gateway`（双向 WS 连接）
- 配置：`appId` + `clientSecret`
- 有独立的 `bridge/`（SDK → 引擎适配）和 `engine/`（协议处理）分层
- 引擎目录结构：
  ```
  engine/
    gateway/     ← HTTP/WS 连接管理、消息队列、重连逻辑
    messaging/   ← 消息收/发/发送者管理
    commands/    ← 斜杠命令
    session/     ← 会话管理
    group/       ← 群组逻辑
    utils/       ← 诊断、音频等
  ```

### 钉钉

- 接入方式：Stream 模式推送或 Webhook
- 签名：带加签密钥的计算验证
- 扩展位于 `extensions/alibaba/`

### 飞书

- 接入方式：App ID + Secret，事件订阅
- 需要管理 `tenant_access_token` 生命周期

### Webhooks（通用，无平台）

- `extensions/webhooks/` 提供通用 HTTP webhook 模板
- 适用于只需接收 POST 回调的简单场景
- 实现：`messaging` + 最小配置

## 消息标准化流程

```
平台原始消息（Telegram JSON / WeChat XML / DingTalk Stream）
  ↓ channel.message-adapter
统一 MessageEvent {
  channel: "telegram",
  sender: { id, name },
  chatType: "direct" | "group",
  text: string,
  media: [{ type, url, localPath }],
  replyToMessageId?: string,
}
  ↓
路由引擎（routing rules）
  ↓
AI Agent 处理
  ↓
outbound adapter 转换回平台格式 → 发送
```

## 会话隔离模式

```typescript
// session key = 平台 + 对话 + 用户
"telegram:chat_12345:user_67890"
"qqbot:group_abc:user_xyz"
// 同一个用户在不同群组 = 不同 session
// 不同用户在同一群组 = 不同 session
```

## 对知识库项目的参考价值

| OpenClaw 模式 | 可借鉴部分 | 不需要的部分 |
|------|------|------|
| ChannelPlugin 接口 | 单一接口 + 多适配器组合 | 不需要 35 个适配器，只需 WeCom 一个 |
| 消息标准化 | 把 WeChat XML 回调转成内部 struct | N/A |
| gateway 模式 | HTTP webhook 接收 → 异步处理 → 回复 | 不需要 WS 双向连接 |
| config schema（Zod） | 类型安全的配置验证 | N/A |
| 会话隔离 | `channel:chat:user` 组合键 | 单人使用不需要复杂路由 |
| setup wizard | 扫码/一键配置流程 | 个人使用手动配就行 |

## 相关

- [[Wiki 服务化部署方案]]
- [[LLM Wiki 模式]]
- [[MCP Vision Server 方案]]
- [[Wiki 目录]]
