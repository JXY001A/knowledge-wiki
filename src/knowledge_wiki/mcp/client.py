"""MCP HTTP 客户端 — 用于 webhook 调用本地 MCP 工具."""

import json
import urllib.request
import urllib.error


MCP_BASE = "http://localhost:9300/mcp"


def call_tool(tool_name: str, args: dict, timeout: int = 60) -> str | None:
    """初始化 MCP 会话并调用工具，返回文本内容."""
    accept = "application/json, text/event-stream"
    hdr = {"Content-Type": "application/json", "Accept": accept}

    try:
        # 1. Initialize session
        req = urllib.request.Request(MCP_BASE,
            data=json.dumps({"jsonrpc": "2.0", "id": "init", "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "wecom-webhook", "version": "1.0"}}}).encode(),
            headers=hdr)
        with urllib.request.urlopen(req, timeout=15) as resp:
            sid = resp.headers.get("Mcp-Session-Id", "")
        if not sid:
            return None

        # 2. Initialized notification
        req = urllib.request.Request(MCP_BASE,
            data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode(),
            headers={**hdr, "Mcp-Session-Id": sid})
        urllib.request.urlopen(req, timeout=10)

        # 3. Call tool
        body = json.dumps({"jsonrpc": "2.0", "id": "t", "method": "tools/call",
            "params": {"name": tool_name, "arguments": args}}).encode()
        req = urllib.request.Request(MCP_BASE, data=body,
            headers={**hdr, "Mcp-Session-Id": sid})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_data = resp.read().decode()

        for line in raw_data.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "result" in data:
                    for c in data["result"].get("content", []):
                        if c.get("type") == "text":
                            return c["text"]
        return None
    except Exception as e:
        print(f"[mcp] call_tool {tool_name} failed: {e}", flush=True)
        return None


def mcp_query(question: str) -> str | None:
    """通过 MCP 查询 wiki，search 回退 + 全文读取."""
    import re

    # Try query (title+tag match → full content)
    result = call_tool("query", {"question": question})
    if result and "未在 wiki 中找到" not in result:
        return result

    # Fallback: search → get paths → read full pages (strip frontmatter)
    from knowledge_wiki.config import settings
    from knowledge_wiki.wiki.frontmatter import strip_frontmatter

    result = call_tool("search", {"keyword": question})
    if result and "未找到" not in result:
        page_paths = re.findall(r"路径:\s*`([^`]+)`", result)
        if page_paths:
            full_texts = []
            for path in page_paths[:5]:
                fpath = settings.wiki_root / path
                if fpath.exists():
                    text = fpath.read_text()
                    body = strip_frontmatter(text)
                    full_texts.append(f"## {fpath.stem}\n\n{body[:2000]}")
            if full_texts:
                return f"# 查询：{question}\n\n" + "\n\n---\n\n".join(full_texts)
        return result

    return None
