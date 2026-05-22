---
title: 企业微信Bot—MCP检索与模型交互链路
type: synthesis
tags: [企业微信, MCP, 模型交互, RAG, 架构, prompt工程]
created: 2026-05-22
updated: 2026-05-22
sources:
  - "[[知识库系统全链路架构]]"
  - "[[Wiki 服务化部署方案]]"
  - "[[DevMechin（AI 主机）]]"
confidence: high
---

> 深度文档：企业微信 Bot 如何通过 MCP 协议检索知识库，再交由本地 LLM（qwen2.5:3b）整理为结构化 template_card 返回用户，涵盖 MCP 客户端实现、prompt 工程、JSON 修复容错、WeChat 格式约束及模型选型演进。

## 架构总览

```
手机微信 → 企业微信 Bot → POST /webhook (AES-256-CBC)
                              │
                    DevMechin wecom-webhook.py
                              │
                   ┌──────────┴──────────┐
                   │                     │
              文本消息 (? 开头)         其他消息
                   │                     │
           _handle_query()         _save_to_inbox()
                   │                 → git push
                   │
       ┌───────────┴───────────┐
       │  MCP Client (HTTP)    │  ←─ 新增，替换旧 grep 方案
       │  localhost:9300/mcp   │
       └───────────┬───────────┘
                   │
       ┌───────────┴───────────┐
       │  wiki-mcp-server      │
       │  query() / search()   │
       └───────────┬───────────┘
                   │ 返回 wiki 页面全文
       ┌───────────┴───────────┐
       │  qwen2.5:3b (Ollama)  │  ←─ 升级，替换旧 1.5B 模型
       │  _call_llm_json()     │
       └───────────┬───────────┘
                   │ JSON: {summary, cards: [{title, summary, details}]}
       ┌───────────┴───────────┐
       │  _send_template_card()│  ×N（800ms 间隔）
       │  _send_markdown()     │  （补充概述）
       └───────────────────────┘
```

## MCP 客户端实现

wecom-webhook 内嵌了一个最小 MCP streamable HTTP 客户端，约 40 行代码。

### 协议流程

```
1. POST /mcp → initialize
   {"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05",...}}
   ← 200 + Mcp-Session-Id header

2. POST /mcp → notifications/initialized
   {"jsonrpc":"2.0","method":"notifications/initialized"}
   ← 202 Accepted

3. POST /mcp → tools/call
   {"jsonrpc":"2.0","method":"tools/call","params":{"name":"query","arguments":{...}}}
   ← SSE: data: {"jsonrpc":"2.0","result":{...}}
```

### 关键约束

**Accept header 必须同时包含两种格式**，否则 MCP server 返回 406：

```python
accept = "application/json, text/event-stream"
```

### 双层检索回退

```python
# 第1层: query — 标题+标签匹配，返回页面全文（800字/页）
result = mcp_call("query", {"question": question})
if result and "未找到" not in result:
    return result

# 第2层: search — 全文 grep 搜索，返回页面路径+摘录
result = mcp_call("search", {"keyword": question})
# 根据路径读完整页面（2000字/页，去 frontmatter）
for path in parse_paths(result):
    full_texts.append(read_full_page(path))
```

旧方案是 py 代码直接 `grep wiki/*.md`，关键字+路径权重打分。新方案走 MCP，但保留了同样的本地回退逻辑（MCP 失败时仍可 grep）。

## 模型交互

### 模型选型演进

| 阶段 | 模型 | 问题 |
|------|------|------|
| v1 | qwen2.5:1.5b / llama3.2:1b | 1.5B 中文理解弱，1B 更差；JSON 格式经常出错 |
| v2 | qwen3:4b | thinking 模型，4000 tokens 全被思考过程吃掉，content 为空 |
| **v3（当前）** | **qwen2.5:3b** | 无 thinking 问题，JSON 输出稳定，中文能力强 |

### LLM 调用函数

当前保留两个 LLM 函数：

| 函数 | 用途 | 参数 |
|------|------|------|
| `_call_llm_json(question, context)` | 生成结构化 JSON 卡片 | `num_predict=2000, temperature=0.1, timeout=60s` |
| `_call_llm_short(question, context)` | 单句摘要（card summary 为空时的回退） | `num_predict=120, temperature=0.1, timeout=30s` |

已删除的死函数：`_call_llm_detailed`（qwen2.5:1.5b markdown 输出）、`_call_llm_fallback`（llama3.2:1b）、`_call_llm`（llama3.2:1b RAG 回退）、`_rag_query`。

### Prompt 工程

**JSON 卡片 prompt**（`_call_llm_json`）：

```
Output ONLY valid JSON. No other text.
Format: {"summary":"整体概述","cards":[{"title":"分类","summary":"100-200字摘要",
  "details":[["键名","值"],["键名2","值2"]]}]}

CRITICAL: details must be an array of 2-element arrays: [["k","v"],["k","v"]].
NEVER use objects like {"键":"k","值":"v"} in details.

Rules:
- summary: one-sentence overall answer (Chinese, 50-100 chars).
- cards: split into 2-5 logical categories.
- Each card: 3-8 detail pairs. Use real data only.
- Always respond in Chinese.
```

**Prompt 设计原则**：

1. **`Output ONLY valid JSON`** — 防止模型在 JSON 前后加解释文字
2. **`CRITICAL` + `NEVER`** — 双层强调 format 约束，防止模型用 dict 格式代替 array
3. **`2-5 logical categories`** — 控制卡片数量，过多会导致单卡内容稀疏
4. **`3-8 detail pairs`** — 控制 detail 密度，太少无聊，太多触达微信 10 条上限
5. **`Real data only. No placeholders.`** — 防止模型编造“请参考相关资料”这类空内容

### JSON 修复容错

即使 prompt 约束严格，小模型仍会产出格式瑕疵。`_call_llm_json` 实现了多层修复：

```python
# 1. 去除 markdown 代码块标记
content_clean = re.sub(r"```(?:json)?\s*", "", content_clean)

# 2. 括号匹配提取 JSON（容忍前后多余文字）
start = content_clean.find("{")
for i, ch in enumerate(content_clean[start:], start):
    if ch == "{": depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            json_str = content_clean[start:i + 1]

# 3. 直接 parse，失败则修复常见错误
fixed = re.sub(r",\s*([}\]])", r"\1", json_str)  # trailing commas
fixed = re.sub(r"([{,])\s*([a-zA-Z_]+)\s*:", r'\1"\2":', fixed)  # unquoted keys
```

### details 格式兼容

模型可能输出多种 details 格式，`_normalize_details()` 统一处理：

```python
# [[k,v], [k,v]]         → 标准 array
# [{k:v}, {k:v}]         → dict 格式
# [{"键":"k","值":"v"}]   → 中文 labeled dict
# [{"key":"k","value":"v"}] → 英文 labeled dict
```

同时做 key 截断 20 字、value 截断 60 字，避免超微信限制。

### 上下文清洗

wiki 页面含 YAML frontmatter（`type`, `tags`, `sources`），模型会将这些元数据当成正文输出。在喂给 LLM 前必须剥离：

```python
def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].strip()
    return text
```

## 输出管道

### template_card 发送

```python
cards = card_data["cards"]
for i, card in enumerate(cards[:8]):
    if i > 0:
        time.sleep(0.8)  # 关键：防止企业微信服务器重排卡片顺序
    _send_template_card(user_id,
        title=card["title"],
        summary=card["summary"],
        details=_normalize_details(card["details"]),
        source_desc=f"{top_page} ({i+1}/{len(cards)})")
```

**800ms 间隔的必要性**：企业微信不保证模板卡片顺序送达，多张卡片几乎同时发送会导致顺序混乱。800ms 间隔经实测可保证顺序。

### 补充 markdown

卡片发送后，如有 `summary` 整体概述（>100 字），额外发一条 markdown 消息：

```python
overall = card_data.get("summary", "")
if overall and len(overall) > 100:
    clean = _clean_markdown(overall)
    _send_markdown(user_id, clean)
```

### WeChat 格式清洗

`_clean_markdown()` 做企业微信兼容处理：

```python
text = re.sub(r"```[\s\S]*?```", lambda m: "[代码]", text)  # 代码块→标记
# 过滤表格行（不支持表格渲染）
if re.match(r"^[\s|:\-]+$", s): continue
text = re.sub(r"<[^>]+>", "", text)  # 去 HTML
```

### template_card 错误码

| 错误 | 原因 | 修复 |
|------|------|------|
| 42035 `Invalid Size` | details key/value 超长或超量 | 截断 20/60 字，最多 10 对 |
| 42035 `Invalid Size` | 空值 | `_normalize_details` 过滤空字符串 |

## 完整处理时序

以下以 `? DevMechin` 为例，记录一次完整查询的时序：

```
t=0.0s   微信发送 "? DevMechin"
t=0.5s   企业微信 POST webhook，webhook 解密 XML
t=0.6s   启动后台线程 _process()
t=0.6s   _handle_query() 开始
t=0.7s   MCP initialize → Session ID
t=0.7s   MCP notifications/initialized
t=0.8s   MCP tools/call query("DevMechin") → 找到 DevMechin（AI 主机）
t=0.9s   剥离 frontmatter，组装 context（~2000字）
t=1.0s   POST localhost:11434/api/chat → qwen2.5:3b
t=6.0s   Ollama 返回 JSON（~5s 推理）
t=6.1s   JSON 解析成功，提取 3-5 张卡片
t=6.2s   卡片1 发送
t=7.0s   卡片2 发送（800ms 间隔）
t=7.8s   卡片3 发送
t=8.6s   卡片4 发送
t=9.0s   Supplementary markdown 发送
        用户看到结果
```

总延迟约 **8-10 秒**，其中 Ollama 推理占 ~5s，客户端发送间隔占 ~3s。

## 相关

- [[知识库系统全链路架构]]
- [[Wiki 服务化部署方案]]
- [[DevMechin（AI 主机）]]
- [[Ollama]]
- [[MCP（Model Context Protocol）]]
- [[Wiki 目录]]
