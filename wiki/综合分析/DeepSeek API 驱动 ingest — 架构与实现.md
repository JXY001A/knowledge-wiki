---
title: DeepSeek API 驱动 ingest — 架构与实现
type: synthesis
tags: [知识工程, Agent, DeepSeek, ingest, 架构]
created: 2026-05-23
updated: 2026-05-23
sources:
  - "[[资料摘要：Agent技术范式演变]]"
  - "[[知识库系统全链路架构]]"
  - "[[AI 自进化知识系统 — 建设路线图]]"
confidence: high
---

> 从企业微信发送 URL 到高质量 wiki 页面生成的全自动 ingest 管线设计与关键实现。DeepSeek API 替代本地 qwen2.5:3b，输出质量从“勉强可用”跃升到接近 Claude Code 水平。

## 一、架构总览

```
企业微信 URL
      │
      ▼
┌─────────────────────────────────────────────────────┐
│              _handle_url_ingest()                     │
│                                                       │
│  Step 1: _fetch_url_text(url)                         │
│    ├─ urllib 下载网页                                  │
│    ├─ og:title → h1 → <title> 提取标题                 │
│    ├─ 去除 script/style/nav/footer/header 标签           │
│    └─ 输出: # 标题\n\n正文（≤50KB）                      │
│                                                       │
│  Step 2: _save_to_inbox(raw_text)                      │
│    └─ 保存到 raw/收件箱/wecom-url-{ts}.md              │
│                                                       │
│  Step 3: _call_llm_ingest(raw_text, url)               │
│    ├─ POST https://api.deepseek.com/v1/chat/...        │
│    ├─ Model: deepseek-v4-pro                           │
│    ├─ System prompt: 11 条规则 + JSON schema            │
│    ├─ Input: 前 40000 字符                              │
│    └─ 输出: 结构化 JSON                                 │
│                                                       │
│  Step 4: _build_source_page(data, url)                 │
│    ├─ templates/source.md 模板 → frontmatter + 正文      │
│    └─ 保存到 wiki/资料摘要/{title}.md                   │
│                                                       │
│  Step 5: _build_concept_page(concept) × N               │
│    ├─ 已存在 → 跳过（保留人工编辑）                       │
│    └─ 新建 → wiki/概念/{name}.md                        │
│                                                       │
│  Step 6: _append_op_log(data, url, title)               │
│    └─ 追加到 wiki/操作日志.md                            │
│                                                       │
│  Step 7: _git_push(ingest: {title})                     │
│    └─ git add -A && git commit && git push             │
└─────────────────────────────────────────────────────┘
      │
      ▼
  企业微信通知: ✅ 已摄取 + 摘要卡片
```

## 二、输入/输出数据流

### 输入：原始网页

```
_fetch_url_text(url) → raw_text (≤50KB markdown)

示例:
# Agent核心技术概念与范式发生了哪些演变以及背后的思考
- 来源: https://mp.weixin.qq.com/s/...
- 时间: 2026-05-22 23:53

Agent核心技术概念与范式发生了哪些演变以及背后的思考 ...
```

### 中间：LLM 结构化 JSON

```json
{
  "title": "资料摘要：Agent技术范式演变",
  "domain": "Agent",
  "tags": ["范式", "智能体", "深度", "观点"],
  "summary": "本文系统梳理了2023至2026年Agent核心技术概念的演变逻辑...",
  "key_points": [
    "Agent经历被动ReAct、工作流、自主规划、自进化四个阶段...",
    "Prompt从紧耦合的单体System Prompt转向渐进式加载的上下文工程..."
  ],
  "notes": "## Agent发展的四个阶段\n\n### 阶段一...",
  "quotes": "今天的Agent依然由Prompt、Planning、Memory等经典模块组成...",
  "concepts": [
    {
      "name": "ReAct架构",
      "definition": "Reasoning+Acting，大模型推理与行动交替执行的Agent基础架构",
      "importance": "奠定了LLM Agent的基本范式，是后续所有演进的起点"
    }
  ],
  "related_pages": ["[[LLM Wiki 模式]]", "[[Agent Skill]]"]
}
```

### 输出：wiki 页面

```
wiki/
├── 资料摘要/资料摘要：Agent技术范式演变.md   ← source 页面
├── 概念/ReAct架构.md                        ← 新建概念页
├── 概念/Agentic Workflow.md                 ← 新建概念页
├── 概念/自进化Agent.md                       ← 新建概念页
├── ...
├── Wiki 目录.md                              ← 更新
└── 操作日志.md                               ← 追加
```

## 三、关键实现细节

### 3.1 DeepSeek API 调用（_call_llm_ingest）

**位置**：`wecom-webhook.py:342-432`

```python
def _call_llm_ingest(content: str, url: str) -> dict | None:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    system_prompt = (
        "你是知识库管理助手。阅读网页内容，输出结构化 JSON 用于生成 wiki 页面。\n\n"
        "## 输出格式\n\n"
        "严格输出以下 JSON 结构，不要 markdown 代码块：\n"
        '{"title":"资料摘要：<10字主题>","domain":"<领域>",'
        '"tags":["标签1","标签2","标签3"],'
        '"summary":"<100-150字摘要>",'
        '"key_points":["要点1","要点2","要点3","要点4"],'
        '"notes":"<详细笔记，800-1500字>",'
        '"quotes":"<关键引用>",'
        '"concepts":[{"name":"概念名",'
        '"definition":"≤50字定义",'
        '"importance":"为什么重要"}],'
        '"related_pages":["[[相关页面]]"]}\n\n'
        "## 规则\n\n"
        "1. title: 必须以\"资料摘要：\"开头，后接10字以内的核心主题\n"
        "2. domain: 从13个预定义领域中选最匹配的1个\n"
        "3. tags: 3-5个，优先从受控词汇表选择\n"
        "4. 所有内容使用中文\n"
        "5. 严格基于原文，不编造信息\n"
        "... (共 11 条规则)"
    )

    body = json.dumps({
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content[:40000]},
        ],
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 4096,
    }).encode()

    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
        raw_content = result["choices"][0]["message"]["content"]
```

**JSON 提取策略**：

```python
# 1. 清除 markdown 代码块标记
raw_content = re.sub(r"```(?:json)?\s*", "", raw_content)
raw_content = re.sub(r"```", "", raw_content)

# 2. Brace-matching：逐字符扫描，找到第一个完整 JSON 对象
start = raw_content.find("{")
depth = 0
for i, ch in enumerate(raw_content[start:], start):
    if ch == "{": depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            return json.loads(raw_content[start:i + 1])
```

此策略比正则 `{.*}` 更健壮：正确处理嵌套对象（如 concepts 数组中的 `{name, definition, importance}`）。

### 3.2 网页内容提取（_fetch_url_text）

**位置**：`wecom-webhook.py:289-339`

```python
# 标题提取优先级：og:title > h1#activity-name > h1 > <title>
for pattern in [
    r'<meta\s+property="og:title"\s+content="(.*?)"',
    r'<h1[^>]*?id="activity-name"[^>]*>(.*?)</h1>',
    r"<h1[^>]*>(.*?)</h1>",
    r"<title>(.*?)</title>",
]:
    m = re.search(pattern, html_data, re.IGNORECASE | re.DOTALL)
    if m:
        title = html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip())
        if title: break

# 去除噪音标签
for tag in ["script", "style", "nav", "footer", "header"]:
    html_data = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "",
                       html_data, flags=re.DOTALL | re.IGNORECASE)

# 去除剩余 HTML 标签 → HTML 实体解码 → 空白压缩 → ≤50KB 截断
text = re.sub(r"<[^>]+>", "\n", html_data)
text = html_mod.unescape(text)
if len(text) > 50000:
    text = text[:50000] + "\n\n...(内容已截断)"
```

**微信公众号兼容**：微信公众号标题不在 `<title>` 中，而在 `<h1 id="activity-name">` 或 `<meta property="og:title">`。优先级链依次尝试，确保提取成功。

### 3.3 资料摘要页生成（_build_source_page）

**位置**：`wecom-webhook.py:435-501`

严格按 `templates/source.md` 构造：

```
---
title: {title}
type: source
tags: [...]
source_url: {url}
---
> {summary}

## 核心要点
- {key_point 1}
- ...

## 详细笔记
{notes}        ← LLM 生成的 800-1500 字 markdown

## 引用与数据
{quotes}

## 相关
- [[Concept A]]   ← 从 concepts 数组提取
- [[Concept B]]
- [[Wiki 目录]]
```

**兼容处理**：concepts 字段支持两种格式——

```python
# 格式 1 (DeepSeek 新格式)：dict list
[{"name": "ReAct架构", "definition": "...", "importance": "..."}]

# 格式 2 (qwen 旧格式)：string list
["ReAct架构", "Workflow"]
```

### 3.4 概念页自动生成（_build_concept_page）

**位置**：`wecom-webhook.py:504-549`

```python
def _build_concept_page(concept: dict) -> Path | None:
    name = concept.get("name", "")
    filepath = dest_dir / f"{name}.md"

    if filepath.exists():
        return None  # 已存在则跳过，保护人工编辑

    # 构造概念页：frontmatter + 定义 + 为什么重要
    page = f"""---
title: {name}
type: concept
tags: [概念]
---
> {definition}

## 是什么
{definition}

## 为什么重要
{importance}
"""
```

**设计决策**：跳过已存在的概念页，而不是覆盖。人工编辑的概念页（如 `渐进式披露.md` 50 行详细内容）比自动生成的 stub 有价值得多。

### 3.5 操作日志追加（_append_op_log）

**位置**：`wecom-webhook.py:565-594`

```python
entry = f"""
## [{today}] ingest | {page_title}

- 来源：{url}
- 新建页面：[[{page_title}]]
- 新增概念：{concept_wikilinks}
- 领域：{domain}
- 核心洞察：{summary}
"""
# 在 "> 每次 ingest" 标记后插入，保持头部说明在前
```

### 3.6 环境注入

API key 通过 systemd service 环境变量注入，不硬编码到脚本中：

```
# ~/.config/systemd/user/wecom-webhook.service
[Service]
Environment=DEEPSEEK_API_KEY=sk-xxx
```

脚本中通过 `os.environ.get("DEEPSEEK_API_KEY")` 读取。

## 四、模型切换前后对比

| | qwen2.5:3b (前) | DeepSeek V4 Pro (后) |
|---|---|---|
| **模型规模** | 3B | 685B (MoE) |
| **输入限制** | 3,000 字符 | 40,000 字符 |
| **Schema 遵循** | 不可靠（长文本忽略指令） | 严格遵循 |
| **标题** | 全文标题重复粘贴 | 精简 10 字核心主题 |
| **领域分类** | 经常输出"其他" | 准确命中 |
| **笔记质量** | ~200 字简单摘要 | 800-3,300 字结构化整理 |
| **概念提取** | 3 个字符串 | 5 个含定义的 dict |
| **页面体积** | ~600 字符 | 4,600+ 字符 |
| **成本** | 免费 | ~¥0.01/篇 |

## 五、错误处理

```
_fetch_url_text 失败
  → 保存 URL 引用到收件箱
  → 通知用户 "⚠️ 无法下载链接内容"

_call_llm_ingest 失败 / JSON 解析失败
  → 原文已保存到 raw/（_save_to_inbox 在 LLM 调用之前执行）
  → 通知用户 "⚠️ LLM 分析失败，已保存原文"
  → 可手动在 Claude Code 中 ingest

_git_push 失败
  → 静默忽略（不影响用户通知）
  → git 变更保留在本地，下次 push 补交
```

## 六、模型选择考量

| 指标 | DeepSeek API | Claude API | 本地 qwen2.5:14b |
|------|-------------|-----------|-------------------|
| 中文质量 | 优秀 | 优秀 | 良好 |
| 128K 上下文 | 是 | 是 | 是（但长文本退化） |
| 指令遵循 | 强 | 极强 | 中 |
| 成本 | ¥0.01/篇 | ¥0.05/篇 | 免费 |
| 可达性 | 需网络 | 需网络 | 本地 |

选择 DeepSeek API 的理由：在 ingest 场景下性价比最优。中文质量与 Claude 同级，成本仅为其 1/5，且已在 Phase 1 的生产环境中验证通过。

## 相关

- [[资料摘要：Agent技术范式演变]]
- [[AI 自进化知识系统 — 建设路线图]]
- [[知识库系统全链路架构]]
- [[资料摘要：DeepSeek API 定价]]
- [[Wiki 目录]]
