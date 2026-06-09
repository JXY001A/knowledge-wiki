---
title: AI 助手全面升级执行方案
type: synthesis
tags: [路线图, 规划, 自进化, 执行方案]
aliases: [全面升级方案]
created: 2026-06-09
updated: 2026-06-09
sources:
  - "[[AI 自进化知识系统 — 总体路线图]]"
  - "[[AI 助手能力补全方案]]"
  - "[[个人AI助手扩展设计方案]]"
  - "[[个人全能助手优化方案]]"
confidence: high
---

> 合并两份独立分析（代码审查 + 能力评估），产出统一执行方案。目标：将 knowledge-wiki 从"功能完备但智能不足"推进到"真·全能 AI 助手"。

## 一、现状诊断

```
                        当前    目标
知识库内容质量           ████░░  丰富、准确、有引用
知识问答智能度           ███░░░  语义理解、多轮对话、带引用
个人助手主动性           ██░░░░  主动推送、智能提醒、洞察报告
自进化闭环               ███░░░  自动检测→自动补充→验证回升
交互体验                 ███░░░  流式输出、语音交互、Markdown 渲染
工程健壮性               █████░  重试机制、超时控制、统一配置、完整测试
```

## 二、执行路线

```
阶段 1：基础稳固（1-2 天）     阶段 2：智能跃升（3-5 天）     阶段 3：体验升级（1-2 周）
─────────────────────────────────────────────────────────────────────────
XSS + Markdown 渲染           语义检索（embedding）         流式响应
多轮对话上下文                DeepSeek query + 带引用回答     多渠道统一会话
检索上下文截断修复            知识库优先 + 通用兜底          用户画像注入查询
意图 fallback 修复            日报/晚报主动推送              质量反馈闭环
LLM 重试 + 超时               截止日期推送通知                语音 I/O（ASR+TTS）
模型配置统一                  闭环自动摄取                    日历集成
清理死代码                    知识深度加工                    主动洞察推送
测试补全                                                      技能自优化
```

## 阶段 1：基础稳固（1–2 天）

### 1.1 XSS 漏洞 + Markdown 渲染（45min）

**位置**：`web/src/pages/Chat.tsx`

**问题**：`dangerouslySetInnerHTML` 无消毒，LLM 输出中的 `<script>` / `<img onerror>` 可执行恶意代码。同时 Markdown 渲染退化——代码块、列表、链接、表格全部丢失。

**方案**：

```bash
cd web && npm install react-markdown rehype-sanitize remark-gfm
```

```tsx
// Chat.tsx — 替换 dangerouslySetInnerHTML
import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'

// 替换：
// <div dangerouslySetInnerHTML={{ __html: m.text.replace(/\n/g, '<br>')... }} />
// 为：
<ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
  {m.text}
</ReactMarkdown>
```

**验证**：发送含 `<script>alert(1)</script>`、代码块、表格的消息，确认 XSS 被拦截、Markdown 正确渲染。

---

### 1.2 多轮对话上下文注入（1h）

**位置**：`webhook/app.py:136` + `webhook/process.py:164`

**问题**：`/chat` 端点不读历史，每条消息独立处理。用户说"详细说说上一点"系统无法理解。DB 已建 conversations 表但从未使用。

**方案**：

```python
# app.py — 修改 chat_api
# 增加 conversation_id 参数
conv_id = data.get("conversation_id", "")
history = []
if conv_id:
    history = _load_recent_messages(conv_id, limit=10)

# process.py — 注入历史到 LLM 调用
def build_context_with_history(question, history, wiki_context):
    history_text = ""
    for m in history[-10:]:
        role = "用户" if m["role"] == "user" else "助手"
        history_text += f"{role}：{m['content']}\n"
    return f"## 对话历史\n{history_text}\n## 知识库检索\n{wiki_context}\n## 当前问题\n{question}"
```

**前端改动**：`Chat.tsx` 发送时附带 `conversation_id`（已有，在 `saveConv` 返回的 `id`）。

**企微渠道**：按 `user_id` + 5 分钟超时自动创建/接续会话。

---

### 1.3 检索上下文截断修复（15min）

**位置**：`agent/skills/query-knowledge/impl.py:57`

**问题**：检索管线精心设计了三层组装（8000 token 预算），但被硬截断为 `full_context[:3000]` 字符，约 80% 被丢弃。

**方案**：

```python
# 改前：full_context = context[:3000]
# 改后：按 LLM 上下文窗口动态分配
MAX_CONTEXT_CHARS = 12000  # qwen2.5:3b 支持 32K tokens，用 1/3 给上下文
full_context = context[:MAX_CONTEXT_CHARS]
```

---

### 1.4 意图 fallback 修复（15min）

**位置**：`webhook/process.py:207-213`

**问题**：LLM 分类+关键词匹配都失败后，非 `?` 前缀消息被静默保存为笔记。用户发"GPU 性能优化技巧"会被当笔记存而不是查询。

**方案**：调整 fallback 优先级——非命令类消息默认走 query：

```python
if not skill:
    if stripped.startswith("?"):
        execute_skill("query-knowledge", ctx)
    elif is_url(stripped):
        execute_skill("ingest-article", ctx)
    else:
        # 优先查询知识库，查询无结果再存笔记
        execute_skill("query-knowledge", ctx)
```

---

### 1.5 LLM 调用韧性（30min）

**位置**：`llm/ollama.py`、`llm/deepseek.py`、`skill/planner.py`

**问题**：所有 LLM 调用无重试、无超时控制、错误只 print 不 log。

**方案**：

| 问题 | 方案 | 位置 |
|------|------|------|
| 无重试 | `urllib` → `httpx`，加 exponential backoff（2 次） | `deepseek.py`、`ollama.py` |
| 无超时 | `planner.py:83-88` 加 `threading.Timer` 30s 超时 | `skill/planner.py` |
| 错误只 print | 统一 `logging.getLogger(__name__)` | 全局 |

---

### 1.6 模型配置统一（15min）

**位置**：`config.py`

**问题**：模型名散落在各模块硬编码（`"qwen2.5:3b"` 在 `ollama.py`、`deepseek.py`、`engine.py` 各出现一次）。

**方案**：统一到 `Settings`：

```python
class Settings(BaseSettings):
    # ... existing ...
    ollama_model_query: str = "qwen2.5:3b"
    ollama_model_classify: str = "llama3.2:1b"  # 意图分类用小模型
    deepseek_model_ingest: str = "deepseek-v4-pro"
    deepseek_model_eval: str = "deepseek-chat"
```

---

### 1.7 清理死代码（15min）

| 文件 | 操作 |
|------|------|
| `skill/router.py` | 删除（`classify_intent_llm` 已替代，router 从未被调用） |
| `process.py` 中的 `handle_query_msg` | 标记 `# DEPRECATED`，1 周后删除 |
| `deepseek.py:37` `os.environ.get` | 统一为 `settings.deepseek_api_key` |

---

## 阶段 2：智能跃升（3–5 天）

### 2.1 语义检索 — 向量补充 BM25（4h）

**位置**：`wiki/retrieval/`

**问题**：纯 BM25 词法匹配，同义词会漏（"注意力机制" vs "Self-Attention"、"大模型" vs "LLM"）。

**方案**：

```
用户问题
  → BM25 关键词检索（快速召回 Top-20）
  → Embedding 语义检索（补充召回 Top-20）
  → RRF (Reciprocal Rank Fusion) 合并去重 → Top-10
  → bge-reranker 精排 → Top-5
  → 分层组装（现有 pipeline）
```

**技术选型**：
- **Embedding**：`bge-small-zh-v1.5`（~90MB，CPU 推理，通过 Ollama 或 `sentence-transformers`）
- **向量存储**：pickle 文件（< 1000 页无需 FAISS）
- **增量索引**：每次 ingest 时自动为新页面生成向量

**新增文件**：
- `wiki/retrieval/embedding.py` — 向量生成 + 搜索
- `wiki/retrieval/fusion.py` — RRF 融合

```python
# embedding.py
class WikiEmbedding:
    def __init__(self):
        self.model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        self.index = {}  # {page_path: vector}
    
    def build_index(self, wiki_dir):
        for page in wiki_dir.glob("**/*.md"):
            text = page.read_text()
            self.index[str(page)] = self.model.encode(text)
    
    def search(self, query, top_k=20):
        q_vec = self.model.encode(query)
        scores = {k: cosine(q_vec, v) for k, v in self.index.items()}
        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]
```

---

### 2.2 DeepSeek Query + 带引用回答（3h）

**位置**：`agent/skills/query-knowledge/impl.py`

**问题**：qwen2.5:3b 回答质量低（评估均分 3.0）。没有引用来源。

**方案**：

```python
# 多级路由
def select_query_model(question, context_len):
    if context_len < 500:
        return "ollama"  # 简单问题用本地
    else:
        return "deepseek"  # 复杂问题用 API

# System prompt 升级
QUERY_PROMPT = """你是个人知识库助手。基于提供的知识库资料回答用户问题。

**要求**：
1. 优先基于知识库资料回答，标注引用来源
2. 知识库无覆盖时，提供通用知识但要明确标注
3. 回答末尾列出参考页面

**输出格式**：
（回答正文，引用用 [[页面名]]）

> 📚 参考：[[页面A]] | [[页面B]]
> 🎯 综合评分：A{accuracy}/C{completeness}/U{usefulness}
"""
```

**回答效果**：

```markdown
## MCP 协议是什么

MCP（Model Context Protocol）是一种 AI 工具调用标准协议，
由 Anthropic 提出……（来源：[[MCP（Model Context Protocol）]]）

当前项目基于 FastMCP 实现了 32 个 MCP 工具……
（来源：[[知识库系统全链路架构]]）

> 📚 参考：[[MCP（Model Context Protocol）]] | [[知识库系统全链路架构]]
```

---

### 2.3 日报/晚报主动推送（1h）

**位置**：`assistant/scheduler.py:178-184` + `agent/skills/daily-brief/impl.py`

**问题**：早晚报只发"发送「早报」查看"，不生成实际内容。用户需手动触发。

**方案**：
1. scheduler 直接调用 `daily-brief` skill 的 `execute()`
2. 日报扩展为 7 个板块：

| 板块 | 内容 |
|------|------|
| 📋 今日待办 | 未完成 + 今日到期，按优先级排序 |
| ⏰ 今日提醒 | 按时序排列 |
| ✅ 习惯打卡 | 今日进度 + 连续天数 |
| 📝 最近笔记 | 昨天/今天新增 |
| 📚 知识库动态 | 昨日新增/更新页面数 |
| 🔖 未读书签 | 超过 7 天未读 |
| 💡 AI 洞察 | "本周你主要关注 XX 领域" |

3. 通过 `_push_to_user()` 推送到企微（基础设施已建好，未使用）

---

### 2.4 截止日期推送（30min）

**位置**：`assistant/scheduler.py:325-341`

**问题**：deadline scan 只写日志，不推送。

**方案**：替换 `_log.info` 为 `_push_to_user()`：

```python
# 改前：
_log.info("%d 个待办即将到期", len(urgent))
# 改后：
_push_to_user(uid, f"⏰ {len(urgent)} 个待办即将到期：\n" + "\n".join(
    f"- {t['title']}（{t['deadline']}）" for t in urgent
))
```

---

### 2.5 知识库优先 + 通用兜底（2h）

**位置**：`agent/skills/query-knowledge/impl.py`

**问题**：wiki 无相关内容时，仍将低相关 BM25 噪声发给 LLM，产出低质回答。

**方案**：

```
用户提问
  → 双路检索（BM25 + Embedding）
  → Top-1 score >= 阈值？
      ├─ 是 → 知识库回答 + 标注引用
      └─ 否 → "知识库暂无覆盖"
               + LLM 通用知识（标注"以下为模型通用知识"）
               + 记录知识缺口到 gap_detector
```

```python
SCORE_THRESHOLD = 0.3  # BM25 低于此分数视为无相关

if top_score < SCORE_THRESHOLD:
    general_answer = call_deepseek(f"用户问题：{question}\n请用通用知识回答，标注'以下为通用知识'")
    record_gap(question, "无相关 wiki 页面")
    return f"⚠️ 知识库暂无覆盖\n\n{general_answer}"
```

---

### 2.6 闭环自动摄取（2h）

**位置**：`evolve/auto_ingest.py`

**问题**：自进化链条在"搜索建议"处断裂，需手动摄取。

**方案**：

```
低分评估 → gap_detector 检测缺口 → 同一 gap 出现 3+ 次
  → auto_ingest_topic() 自动搜索 + DeepSeek 总结
  → 推送通知"已自动补充 XX 领域资料"  
  → 安全阈值：每周最多 5 篇，超出转建议
  → 周报标注已自动补全的 gap
```

---

### 2.7 知识深度加工（2h）

**位置**：`wiki/retrieval/embedding.py`（复用）

**方案**：
1. **语义关联发现**：计算所有 wiki 页面间的余弦相似度，Top-N 建议添加 wikilink
2. **矛盾检测增强**：LLM 驱动（替换规则匹配），对比两篇页面内容

```python
def discover_relations(wiki_dir):
    """发现高相似度但无 wikilink 的页面对，建议关联"""
    pairs = []
    for p1, p2 in combinations(pages, 2):
        sim = cosine_similarity(embeddings[p1], embeddings[p2])
        if sim > 0.7 and not has_wikilink(p1, p2):
            pairs.append((p1, p2, sim))
    return sorted(pairs, key=lambda x: -x[2])[:20]
```

---

## 阶段 3：体验升级（1–2 周）

### 3.1 流式响应（4h）

**问题**：qwen2.5:3b 生成耗时 10+ 秒，用户只看到 spinner。

**方案**：
1. 后端 `/chat` → SSE endpoint（`text/event-stream`）
2. Ollama 开启 `stream=True`
3. 前端 `EventSource` 逐字渲染

```python
# app.py
@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    def generate():
        for chunk in ollama_stream(prompt):
            yield f"data: {json.dumps({'token': chunk})}\n\n"
    return Response(generate(), mimetype="text/event-stream")
```

---

### 3.2 多渠道统一会话（3h）

**问题**：微信、Web、MCP 三个入口各自独立。

**方案**：
- 会话按 `user_id` + `channel` 关联到统一会话表
- 微信按 5 分钟超时自动归属
- Web 端可查看/接续微信发起的对话
- 会话上下文跨渠道共享

---

### 3.3 用户画像注入（1h）

**位置**：`memory/profile.py` → `query-knowledge/impl.py`

**问题**：`USER.md` 已自动生成（活跃领域、使用时段），但从未注入到 LLM。

**方案**：query 的 system prompt 前加画像片段：

```python
profile = get_user_profile(user_id)
profile_prefix = f"用户活跃领域：{profile['domains']}。专业程度：{profile['level']}。"
system_prompt = profile_prefix + QUERY_PROMPT
```

---

### 3.4 质量反馈闭环（2h）

**方案**：eval 结果从 fire-and-forget 升级为驱动行动：

| 触发条件 | 动作 |
|---------|------|
| 单次 score ≤ 2 | 推送"刚才回答质量不高，建议补充 XX 领域" |
| 同领域连续 3 次 ≤ 3 | 自动触发 `auto_ingest_topic()` |
| 周报 | 增加质量趋势图 + 低分领域排行 |

---

### 3.5 语音 I/O（4h）

**方案**：
- **ASR**：企微语音消息（零成本，已接入）+ 本地 `whisper.cpp`（后续）
- **TTS**：已有 `speak-text` skill（edge-tts），加流式播报
- **Web 端**：浏览器 SpeechSynthesis API

---

### 3.6 日历集成 + 主动洞察 + 技能自优化

长期方向，方案见原文。现将基础设施就绪后逐步实施。

---

## 全部任务清单

```
阶段 1 — 基础稳固（1-2 天）
├── 1.1  XSS + Markdown 渲染        web/src/pages/Chat.tsx
├── 1.2  多轮对话上下文              webhook/app.py + process.py
├── 1.3  检索上下文截断修复          agent/skills/query-knowledge/impl.py
├── 1.4  意图 fallback 修复          webhook/process.py
├── 1.5  LLM 调用韧性               llm/* + skill/planner.py
├── 1.6  模型配置统一               config.py
├── 1.7  清理死代码                  skill/router.py 等
└── 1.8  测试补全                    tests/webhook/ + tests/retrieval/

阶段 2 — 智能跃升（3-5 天）
├── 2.1  语义检索（embedding）       wiki/retrieval/embedding.py
├── 2.2  DeepSeek query + 引用回答    agent/skills/query-knowledge/impl.py
├── 2.3  日报/晚报主动推送           assistant/scheduler.py + daily-brief
├── 2.4  截止日期推送                assistant/scheduler.py
├── 2.5  知识库优先 + 通用兜底       agent/skills/query-knowledge/impl.py
├── 2.6  闭环自动摄取                evolve/auto_ingest.py
├── 2.7  知识深度加工                wiki/retrieval/embedding.py（复用）
└── 2.8  Dashboard 知识库质量面板    web/src/pages/Dashboard.tsx

阶段 3 — 体验升级（1-2 周）
├── 3.1  流式响应                    webhook/app.py + Chat.tsx
├── 3.2  多渠道统一会话              webhook/process.py + assistant/db.py
├── 3.3  用户画像注入                query-knowledge/impl.py
├── 3.4  质量反馈闭环                eval/scorer.py
├── 3.5  语音 I/O                    speak-text skill + whisper
├── 3.6  日历集成（长期）
├── 3.7  主动洞察推送（长期）
└── 3.8  技能自优化（长期）
```

## 验收标准

| 阶段 | 关键指标 |
|------|---------|
| 阶段 1 完成 | XSS 修复验证、多轮对话≥5 轮、上下文≥8000 字符、无死代码、所有 LLM 调用有重试 |
| 阶段 2 完成 | 评估均分 ≥4.0、语义近义词命中率 ≥85%、每日早晚报无需手动触发、缺口闭环自动运转 |
| 阶段 3 完成 | 流式首 token < 2s、跨渠道对话连续、语音问答可用、Dashboard 显示质量趋势 |
