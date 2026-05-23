# Skill 规范

> 基于 [agentskills.io](https://agentskills.io) 开放标准，结合 [Claude Code Skill](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills) 和 [Google ADK Design Patterns](https://google.github.io/adk-docs/skills/) 设计。

## 文件结构

每个技能是一个独立目录，最少包含 `skill.json`：

```
skills/<skill-name>/
├── skill.json        # 必需：技能元数据和配置
├── SKILL.md          # 推荐：技能完整定义（Agent 执行时加载） 
├── impl.py           # 可选：Python 实现
├── scripts/          # 可选：辅助脚本
└── references/       # 可选：参考文档
```

## skill.json 格式

```json
{
  "name": "skill-name",
  "version": "1.0",
  "description": "一句话描述技能功能",
  "tier": 1,
  "model": "auto",
  "tools": ["search", "query"],
  "triggers": ["搜索", "search", "查找"],
  "dependencies": ["other-skill"]
}
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 技能唯一标识，kebab-case |
| `version` | string | ✅ | 语义版本号 |
| `description` | string | ✅ | 一句话描述 |
| `tier` | int | ✅ | 加载层级：1=始终加载，2=按需加载，3=懒加载 |
| `model` | string | ✅ | `local` / `deepseek` / `auto` |
| `tools` | string[] | | 依赖的 MCP 工具列表 |
| `triggers` | string[] | | 触发关键词（用户意图匹配） |
| `dependencies` | string[] | | 依赖的其他技能名称 |

## 三级渐进式加载

| 层级 | 加载时机 | 内容 | Token 消耗（每技能） |
|------|---------|------|---------------------|
| Tier 1 | Agent 启动 | name + description | ~50 tokens |
| Tier 2 | 意图匹配后 | SKILL.md 完整正文 | ~500-2000 tokens |
| Tier 3 | 执行需要时 | scripts/ + references/ | 按需 |

## SKILL.md 格式

Tier 2 加载的完整技能定义，遵循以下结构：

```markdown
# 技能名称

简短描述。

## 触发条件

- 用户输入包含以下关键词：...
- 上下文满足以下条件：...

## 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|

## 输出

| 字段 | 类型 | 说明 |
|------|------|------|

## 执行步骤

1. 步骤一
2. 步骤二
3. ...

## 前置依赖

- 依赖的 MCP 工具
- 依赖的其他技能

## 评估标准

- 正确性：...
- 完整性：...
- 性能：...

## 示例

### 输入
...

### 预期输出
...
```

## 模型选择策略

| 任务类型 | 模型 | 理由 |
|---------|------|------|
| 简单查询、信息检索 | local (qwen2.5:3b) | 低延迟、免费 |
| 复杂分析、内容生成 | deepseek (v4-pro) | 高质量、128K 上下文 |
| 图像理解 | local (qwen3-vl:8b) | 本地 GPU 加速 |
| `auto` | 自动判断 | 检测关键词决定 |
