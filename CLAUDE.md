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

Python 项目代码位于 `src/knowledge_wiki/`，按模块组织：

| 模块 | 职责 |
|------|------|
| `src/knowledge_wiki/wiki/` | 共享 wiki 操作：git、frontmatter、搜索、页面构建、日志 |
| `src/knowledge_wiki/llm/` | LLM 客户端：DeepSeek API + Ollama |
| `src/knowledge_wiki/mcp/` | MCP 服务端 + 客户端 + 工具实现 |
| `src/knowledge_wiki/webhook/` | 企业微信 Bot：消息接收、处理、回复 |
| `src/knowledge_wiki/skill/` | Agent 技能系统：注册表、加载引擎、规划器、路由 |
| `skills/` | 文件系统技能注册表（每个 skill 一个目录） |
| `deploy/` | systemd 单元 + 部署脚本 |
| `tests/` | pytest 测试套件 |

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
