# knowledge-wiki — Claude Code Schema

@AGENTS.md

> **本文件仅包含 Claude Code 专属的补充指令。**
>
> 共享 wiki Schema 全部定义在 `AGENTS.md` 中，通过 `@` 导入自动加载。
> **绝不将 AGENTS.md 已有的内容复制到本文件。**
> 需要修改共享规则时，编辑 AGENTS.md，不要在此文件中重新定义。
>
> ingest / lint / query 操作修改的是 wiki 页面，不是 Schema 文件。

## 自动提交

每次 ingest / lint / query 操作完成后，**必须**执行以下流程将知识变更同步到 GitHub：

```bash
git add -A
git diff --staged --quiet || git commit -m "ingest/lint/query: <简要描述>" && git push
```

此提交与 Stop 钩子互斥：本流程完成推送后仓库是干净的，Stop 钩子的 `git diff --staged --quiet` 检查会跳过，不会重复提交。

## 代码结构

```
knowledge-wiki/
├── agent/skills/              # 🤖 智能体技能（每个 skill 一个目录）
├── server/src/knowledge_wiki/ # 🖥️ Python 服务端包
│   ├── wiki/                  # 共享 wiki 操作：git、frontmatter、搜索、页面构建、日志
│   ├── llm/                   # LLM 客户端：DeepSeek API + Ollama
│   ├── mcp/                   # MCP 服务端 + 客户端 + 工具实现
│   ├── webhook/               # 企业微信 Bot：消息接收、处理、回复
│   ├── skill/                 # Agent 技能引擎：注册表、路由、规划器
│   ├── memory/                # 记忆系统：事件记录、搜索、用户画像
│   ├── assistant/             # 个人助理：待办、提醒、笔记、书签、习惯
│   ├── eval/                  # 评估引擎：DeepSeek 评分
│   └── evolve/                # 自进化：缺口检测、自动摄取、报告
├── web/                       # 🌐 React SPA 前端
├── wiki/                      # 📚 知识库 Markdown 页面
├── raw/                       # 📄 不可变原始资料
├── deploy/                    # systemd 单元 + 部署脚本
└── tests/                     # pytest 测试套件
```

### 本地开发

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m pytest tests/ -v
```

### CLI

```bash
python -m knowledge_wiki serve    # 启动 MCP Server（:9300）
python -m knowledge_wiki webhook  # 启动企业微信 Webhook（:9400）
```
