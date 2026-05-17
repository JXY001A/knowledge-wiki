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
