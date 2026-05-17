# 本地部署 VL 模型解析设计稿 — 技术方案

## 一、背景

Claude Code 使用 DeepSeek V4 Pro 纯文本模型（不支持多模态），无法直接读取 UI 设计稿/截图的图片内容。方案思路：本地部署一个视觉语言模型（VL），通过 MCP Server 将图片转为结构化文字描述，再传给 Claude Code 生成代码。

## 二、架构

```
用户上传设计稿 (PNG)
        │
        ▼
┌─────────────────────────┐
│  Claude Code            │
│  调用 describe_design() │
└────────┬────────────────┘
         │ MCP 协议 (stdio)
         ▼
┌─────────────────────────┐
│  MCP Vision Server       │  ← Python 脚本
│  ~/mcp-servers/          │
│  vision-server.py        │
└────────┬────────────────┘
         │ HTTP (base64 图片)
         ▼
┌─────────────────────────┐
│  Ollama                  │  ← 本地推理服务
│  localhost:11434         │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Qwen3-VL:4b            │  ← 视觉语言模型
│  (最终方案)              │
│  LLaVA:7b (当前降级)    │
└────────┬────────────────┘
         │
         ▼
    结构化文字描述
    → 传回 Claude Code → 生成代码
```

## 三、模型选型

### 首选：Qwen3-VL:4b

| 维度 | 说明 |
|------|------|
| **参数量** | ~4B（密集模型） |
| **文件大小** | ~2.7GB（Q4_K_M 量化） |
| **硬件要求** | 8GB RAM，Apple Silicon M 系可跑 |
| **中文能力** | 原生支持，UI 中文文案识别优秀 |
| **Ollama 要求** | v0.12.7+ |
| **许可证** | Apache 2.0 |

### 备选：LLaVA:7b（当前降级方案）

| 维度 | 说明 |
|------|------|
| **参数量** | ~7B |
| **文件大小** | ~4.1GB |
| **中文能力** | 较弱，UI 中文文案识别差 |
| **Ollama 要求** | v0.7.0 即可 |

### Qwen3-VL 全家桶

| 标签 | 参数量 | 文件大小 | 适用场景 |
|------|--------|----------|----------|
| `qwen3-vl:2b` | ~2B | ~1.5GB | 边缘设备 |
| **`qwen3-vl:4b`** ⭐ | ~4B | ~2.7GB | **推荐** — 最佳性价比 |
| `qwen3-vl:8b` | ~8.77B | ~5.5GB | 更强能力，需 8GB+ GPU |
| `qwen3-vl:30b` | 31.1B (MoE) | ~20GB | 服务器/生产环境 |
| `qwen3-vl:235b` | 235B (MoE) | — | SOTA 级，需多卡 |

## 四、实施步骤

### 步骤 1：安装/升级 Ollama

```bash
# 安装（macOS）
brew install --formula ollama

# 如果不能通过 brew 获取最新版，从 GitHub 下载
# 下载二进制包（macOS ARM64）
curl -L "https://github.com/ollama/ollama/releases/download/v0.24.0/ollama-darwin.tgz" \
  -o /tmp/ollama-darwin.tgz

# 解压并替换
tar -xzf /tmp/ollama-darwin.tgz -C /tmp/
sudo cp /tmp/ollama /opt/homebrew/bin/ollama
```

### 步骤 2：启动服务并拉取模型

```bash
# 启动服务
brew services start ollama

# 拉取模型（二选一）
ollama pull qwen3-vl:4b      # 首选（需 Ollama >= 0.12.7）
ollama pull llava:7b          # 备选（兼容旧版 Ollama 0.7.0）
```

### 步骤 3：创建 MCP Vision Server

```bash
# 创建虚拟环境
python3 -m venv ~/mcp-servers/.venv
source ~/mcp-servers/.venv/bin/activate
pip install mcp httpx
```

文件：`~/mcp-servers/vision-server.py`

```python
"""
MCP Vision Server — 调用本地 Ollama VL 模型解析图片为文字描述
"""
import json
import sys
import base64
import asyncio
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"

# 根据实际安装的模型切换
# MODEL = "llava:7b"       # 备选
MODEL = "qwen3-vl:4b"       # 首选

PROMPT = """请详细描述这张UI设计稿/截图，面向一位前端开发工程师：

1. **整体布局**：页面分几个主要区域？它们的空间关系和比例如何？
2. **侧边栏/导航**（如有）：菜单项、按钮、图标、折叠状态
3. **主内容区**：标题文字、副标题。UI组件（输入框、按钮、卡片、表格、列表等）
4. **每个组件的文案**：尽可能一字不差地写出所有可见文字
5. **配色和主题**：背景色、强调色、文字颜色、明暗色倾向
6. **间距和尺寸**：padding、margin、圆角半径、字体大小等
7. **交互状态**：hover、active、disabled、loading等状态暗示
8. **其他细节**：分割线、阴影、渐变、动画效果等

请尽量具体量化，越详细越好。"""

server = Server("vision-server")

async def call_ollama(image_path: str) -> str:
    """读取图片 → base64 → 调 Ollama API → 返回文字描述"""
    img_file = Path(image_path)
    if not img_file.exists():
        return f"错误: 图片文件不存在 — {image_path}"

    img_b64 = base64.b64encode(img_file.read_bytes()).decode()

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": PROMPT,
                "images": [img_b64],
                "stream": False,
            },
        )
        resp.raise_for_status()
    return resp.json()["response"]

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="describe_design",
            description="用本地 VL 模型解析 UI 设计稿/截图，返回结构化文字描述",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "图片文件的绝对路径",
                    }
                },
                "required": ["image_path"],
            },
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "describe_design":
        raise ValueError(f"Unknown tool: {name}")
    result = await call_ollama(arguments["image_path"])
    return [TextContent(type="text", text=result)]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### 步骤 4：注册到 Claude Code

文件：`.mcp.json`（项目根目录）

```json
{
  "mcpServers": {
    "vision": {
      "command": "/Users/jinxianyu/mcp-servers/.venv/bin/python3",
      "args": ["/Users/jinxianyu/mcp-servers/vision-server.py"]
    }
  }
}
```

在 `.claude/settings.local.json` 中授权：

```json
{
  "enabledMcpjsonServers": ["vision"]
}
```

### 步骤 5：使用

重启 Claude Code 后，当用户发送设计稿图片时，Claude Code 会自动调用：

```
describe_design("/Users/jinxianyu/.claude/image-cache/xxx/design.png")
```

模型返回结构化文字描述，Claude Code 据此生成代码。

## 五、当前状态

| 组件 | 状态 | 备注 |
|------|------|------|
| Ollama | ✅ 已安装 v0.7.0 | **需升级到 v0.12.7+** 才能跑 Qwen3-VL |
| LLaVA:7b | ✅ 已下载 | 可用但中文+UI理解弱 |
| Qwen3-VL:4b | ❌ 未下载 | 需要升级 Ollama 后 `ollama pull qwen3-vl:4b` |
| MCP Server | ✅ 已完成 | `~/mcp-servers/vision-server.py` |
| `.mcp.json` | ✅ 已配置 | 项目根目录 |
| 端到端测试 | ✅ 通过 | LLaVA:7b 链路跑通 |

## 六、待办

1. **升级 Ollama** 到 v0.24.0（`ollama-darwin.tgz` 已下载到 `/tmp/`，需手动解压替换）
2. **拉取 Qwen3-VL:4b**：`ollama pull qwen3-vl:4b`
3. **切换模型**：修改 `vision-server.py` 中 `MODEL = "qwen3-vl:4b"`
4. **重启 Claude Code** 加载新 MCP Server

## 七、成本

| 项目 | 说明 |
|------|------|
| Ollama | 免费开源 |
| Qwen3-VL:4b | 免费，Apache 2.0 许可证 |
| MCP Server | 自建，无成本 |
| 推理硬件 | MacBook（Apple Silicon 8GB+）本地运行 |
| 推理速度 | 4b 模型约 5-15 秒/张（取决于硬件） |
| 总成本 | **零** |
