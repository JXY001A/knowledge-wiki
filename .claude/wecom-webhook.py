#!/usr/bin/env python3
"""wecom-bot-webhook — 企业微信 Bot 回调服务，主动发送 Markdown 消息。

部署：DevMechin (192.168.71.127:9400)，frp 穿透至 8.133.175.201:9400

环境变量:
  WECOM_TOKEN / WECOM_AES_KEY / WECOM_CORP_ID  — 消息加解密
  WECOM_SECRET / WECOM_AGENT_ID  — 主动发送消息
"""

import base64
import hashlib
import json
import os
import random
import re
import struct
import socket
import subprocess
import string
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from flask import Flask, request, jsonify

# ---- Config ----
TOKEN = os.environ.get("WECOM_TOKEN", "")
AES_KEY = os.environ.get("WECOM_AES_KEY", "")
CORP_ID = os.environ.get("WECOM_CORP_ID", "")
SECRET = os.environ.get("WECOM_SECRET", "")
AGENT_ID = os.environ.get("WECOM_AGENT_ID", "1000002")
WIKI_ROOT = Path(os.environ.get("WIKI_ROOT", os.path.expanduser("~/code/knowledge-wiki")))
RAW_INBOX = WIKI_ROOT / "raw" / "收件箱"

HOST = os.environ.get("WEBHOOK_HOST", "127.0.0.1")
PORT = int(os.environ.get("WEBHOOK_PORT", "9400"))

app = Flask(__name__)

# ---- Token cache ----
_token_cache: dict = {"token": "", "expires": 0}
_token_lock = threading.Lock()


# ---- WeChat Crypto ----

def _aes_key_bytes() -> bytes:
    return base64.b64decode(AES_KEY + "=")


def _pkcs7_unpad(data: bytes) -> bytes:
    n = data[-1]
    if n < 1 or n > 32:
        raise ValueError("bad PKCS7 padding")
    return data[:-n]


def _decrypt_msg(encrypted: str) -> str:
    from Crypto.Cipher import AES
    aes_key = _aes_key_bytes()
    cipher = base64.b64decode(encrypted)
    cipher_obj = AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16])
    plain = cipher_obj.decrypt(cipher)
    plain = _pkcs7_unpad(plain)
    msg_len = socket.ntohl(struct.unpack("I", plain[16:20])[0])
    msg = plain[20:20 + msg_len].decode("utf-8")
    corp_id = plain[20 + msg_len:].decode("utf-8")
    if corp_id != CORP_ID:
        raise ValueError(f"CorpID mismatch: {corp_id} != {CORP_ID}")
    return msg


def _verify_signature(signature: str, timestamp: str, nonce: str, echostr: str) -> bool:
    params = sorted([TOKEN, timestamp, nonce, echostr])
    return hashlib.sha1("".join(params).encode()).hexdigest() == signature


# ---- WeChat API (Active Messaging) ----

def _get_access_token() -> str:
    """Get cached or fresh WeChat API access token."""
    global _token_cache
    now = time.time()
    with _token_lock:
        if _token_cache["token"] and _token_cache["expires"] > now + 60:
            return _token_cache["token"]

    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={SECRET}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            token = data.get("access_token", "")
            expires = now + data.get("expires_in", 7200)
            with _token_lock:
                _token_cache = {"token": token, "expires": expires}
            return token
    except Exception as e:
        print(f"[wecom] gettoken failed: {e}", flush=True)
        return ""


def _send_markdown(user_id: str, content: str) -> bool:
    """Send markdown message to user via WeChat API."""
    token = _get_access_token()
    if not token:
        return False

    body = json.dumps({
        "touser": user_id,
        "msgtype": "markdown",
        "agentid": int(AGENT_ID),
        "markdown": {"content": content},
    }).encode()

    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            ok = data.get("errcode") == 0
            if not ok:
                print(f"[wecom] send failed: {data}", flush=True)
            return ok
    except Exception as e:
        print(f"[wecom] send error: {e}", flush=True)
        return False


def _send_template_card(user_id: str, title: str, summary: str,
                        details: list[tuple[str, str]] | None = None,
                        jump_title: str = "", jump_url: str = "",
                        source_desc: str = "知识库") -> bool:
    """Send template_card (text_notice) to user."""
    token = _get_access_token()
    if not token:
        return False

    card = {
        "card_type": "text_notice",
        "source": {"desc": source_desc, "desc_color": 0},
        "main_title": {"title": title, "desc": summary},
    }

    if details:
        card["horizontal_content_list"] = [
            {"keyname": k, "value": v} for k, v in details[:10]
        ]
        if len(details) > 10:
            card["sub_title_text"] = f"等 {len(details)} 项关键数据"

    # card_action is required
    if jump_title and jump_url:
        card["jump_list"] = [{"type": 1, "url": jump_url, "title": jump_title}]
        card["card_action"] = {"type": 1, "url": jump_url}
    else:
        card["card_action"] = {"type": 1, "url": "https://work.weixin.qq.com"}

    body = json.dumps({
        "touser": user_id,
        "msgtype": "template_card",
        "agentid": int(AGENT_ID),
        "template_card": card,
    }).encode()

    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            ok = data.get("errcode") == 0
            if not ok:
                print(f"[wecom] template_card failed: {data}", flush=True)
            return ok
    except Exception as e:
        print(f"[wecom] template_card error: {e}", flush=True)
        return False


# ---- MCP Client ----

def _mcp_query(question: str) -> str | None:
    """Call wiki-mcp query tool on localhost:9300 via MCP streamable HTTP.

    Returns raw markdown context from matching wiki pages, or None on failure.
    """
    base = "http://localhost:9300/mcp"
    hdr = {"Content-Type": "application/json"}

    try:
        # 1. Initialize session
        req = urllib.request.Request(base,
            data=json.dumps({"jsonrpc": "2.0", "id": "init", "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "wecom-webhook", "version": "1.0"}}}).encode(),
            headers=hdr)
        with urllib.request.urlopen(req, timeout=15) as resp:
            session_id = resp.headers.get("Mcp-Session-Id", "")
        if not session_id:
            return None

        # 2. Send initialized notification
        req = urllib.request.Request(base,
            data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode(),
            headers={**hdr, "Mcp-Session-Id": session_id})
        urllib.request.urlopen(req, timeout=10)

        # 3. Call query tool
        req = urllib.request.Request(base,
            data=json.dumps({"jsonrpc": "2.0", "id": "q", "method": "tools/call",
                "params": {"name": "query", "arguments": {"question": question}}}).encode(),
            headers={**hdr, "Mcp-Session-Id": session_id, "Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()

        # Parse SSE response
        for line in body.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "result" in data:
                    for c in data["result"].get("content", []):
                        if c.get("type") == "text":
                            return c["text"]
        return None
    except Exception as e:
        print(f"[wecom] MCP query failed: {e}", flush=True)
        return None


# ---- Message Processing ----

def _save_to_inbox(content: str, msg_type: str = "text") -> Path:
    RAW_INBOX.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filepath = RAW_INBOX / f"wecom-{msg_type}-{ts}.md"
    text = f"# 企业微信消息\n\n- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n- 类型: {msg_type}\n\n{content}"
    filepath.write_text(text)
    return filepath


def _git_push(msg: str):
    try:
        subprocess.run(
            f"cd {WIKI_ROOT} && git add -A && git diff --staged --quiet || git commit -m '{msg}' && git push origin main",
            shell=True, capture_output=True, timeout=30,
        )
    except Exception:
        pass


def _process(user_id: str, text: str):
    """Process incoming message: ? for query, else ingest."""
    try:
        if text.strip().startswith("?"):
            question = text.strip()[1:].strip()
            if not question:
                _send_markdown(user_id, "请输入查询内容，如：`? DevMechin GPU`")
                return
            _handle_query(user_id, question)
        else:
            filepath = _save_to_inbox(text, "text")
            _git_push(f"ingest: wecom text {filepath.name}")
            _send_markdown(user_id,
                f"✅ 已保存到知识库\n\n> 文件：`{filepath.relative_to(WIKI_ROOT)}`\n> 可在 Obsidian 或 MCP 中处理 ingest")
    except Exception as e:
        print(f"[wecom] _process error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        _send_markdown(user_id, "处理消息时出错，请重试。")


def _normalize_details(raw: list) -> list[tuple[str, str]]:
    """Normalize LLM details output: supports [[k,v],...], [k,v,k,v,...], [{k:v},...]."""
    if not raw:
        return []
    result = []
    for item in raw:
        if isinstance(item, (list, tuple)):
            if len(item) >= 2:
                result.append((str(item[0]), str(item[1])))
        elif isinstance(item, dict):
            for k, v in item.items():
                result.append((str(k), str(v)))
        elif isinstance(item, str):
            result.append(("", str(item)))
    # If odd count of single strings, pair them
    if len(result) == 0 and all(isinstance(x, str) for x in raw):
        for i in range(0, len(raw) - 1, 2):
            result.append((str(raw[i]), str(raw[i + 1])))
    return result[:10]


def _extract_title_from_page(results: list) -> str:
    """Get the best title from top matching pages."""
    return results[0][1]


def _extract_description(body: str) -> list[str]:
    """Extract description paragraphs from wiki page body.
    Returns list of text paragraphs (first element is the 'title' line)."""
    parts = []
    lines = body.strip().split("\n")
    for line in lines:
        s = line.strip()
        if not s:
            if parts:
                break
            continue
        # Skip headers, tables, code
        if s.startswith("#") or s.startswith("|") or s.startswith("```"):
            if parts:
                break
            continue
        # Extract > quote content
        if s.startswith(">"):
            parts.append(s[1:].strip())
            continue
        parts.append(s)
    return parts


def _extract_summary_from_page(body: str) -> str:
    """Extract first meaningful paragraph from page body."""
    lines = body.strip().split("\n")
    paragraph = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("|") or s.startswith(">") or s.startswith("```"):
            if paragraph:
                break
            continue
        paragraph.append(s)
    return " ".join(paragraph)[:200]


def _extract_first_meaningful_text(body: str) -> str:
    """Get the wiki page's first meaningful paragraph as card description."""
    lines = body.strip().split("\n")
    text_lines = []
    for line in lines:
        s = line.strip()
        if not s:
            if text_lines:
                break
            continue
        if s.startswith("> "):
            text_lines.append(s[2:])
        elif not s.startswith("#") and not s.startswith("|") and not s.startswith("```"):
            text_lines.append(s)
        if len(" ".join(text_lines)) > 200:
            break
    return " ".join(text_lines)[:300]


def _split_by_sections(body: str, page_title: str) -> list[tuple[str, str]]:
    """Split page body by ## section headers. Returns [(section_title, section_body), ...]."""
    sections = []
    current_title = page_title
    current_body = []
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith("## "):
            if current_body:
                sections.append((current_title, "\n".join(current_body)))
            current_title = s[3:].strip()
            current_body = []
        else:
            current_body.append(line)
    if current_body:
        sections.append((current_title, "\n".join(current_body)))
    return sections


def _extract_section_kv(body: str) -> list[tuple[str, str]]:
    """Fallback: extract ## section headers as implicit key-value (section name, first sentence)."""
    import re
    sections = re.split(r"\n##\s+", body)
    pairs = []
    for sec in sections[1:]:
        header_end = sec.find("\n")
        if header_end == -1:
            continue
        key = sec[:header_end].strip()
        rest = sec[header_end:].strip()
        # Get first sentence
        first_line = rest.split("\n")[0].strip()
        if len(first_line) > 5 and len(first_line) < 80:
            pairs.append((key, first_line))
        if len(pairs) >= 6:
            break
    return pairs


def _extract_kv_from_markdown(body: str) -> list[tuple[str, str]]:
    """Extract key-value pairs from markdown tables."""
    import re
    pairs = []
    lines = body.split("\n")
    in_table = False
    headers = []

    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            in_table = False
            headers = []
            continue

        # Skip separator lines
        if re.match(r"^[\s|:\-]+$", s):
            continue

        cells = [c.strip() for c in s.strip("|").split("|")]
        if not headers and len(cells) >= 2:
            headers = cells
        elif headers and len(cells) == len(headers):
            for h, v in zip(headers, cells):
                if h and v and h not in ("---", ":", "-"):
                    pairs.append((h, v))
            break  # Only take first table

    return pairs[:6]


def _find_page_path(title: str) -> str | None:
    """Find the file path for a page title in wiki/."""
    import re as _re
    wiki_dir = WIKI_ROOT / "wiki"
    for md in sorted(wiki_dir.rglob("*.md")):
        text = md.read_text()
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                for line in text[3:end].splitlines():
                    if line.startswith("title:") and title in line:
                        return str(md.relative_to(WIKI_ROOT))
        if title in md.stem:
            return str(md.relative_to(WIKI_ROOT))
    return None


def _clean_markdown(text: str) -> str:
    """Clean LLM markdown for WeChat display."""
    import re
    text = re.sub(r"```[\s\S]*?```", lambda m: "[代码]", text)
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        s = line.strip()
        if re.match(r"^[\s|:\-]+$", s):
            continue
        cleaned.append(line)
    text = "\n".join(cleaned)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _call_llm_short(question: str, context: str) -> str | None:
    """Call qwen3:4b for a short one-sentence summary."""
    try:
        body = json.dumps({
            "model": "qwen3:4b",
            "messages": [
                {"role": "system", "content": "Answer in ONE short Chinese sentence based on the wiki content. No formatting."},
                {"role": "user", "content": f"Wiki:\n{context[:2000]}\n\nQ: {question}"},
            ],
            "stream": False,
            "options": {"num_predict": 120, "temperature": 0.1},
        }).encode()
        req = urllib.request.Request("http://localhost:11434/api/chat", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = json.loads(resp.read()).get("message", {}).get("content", "").strip()
            return content if content and len(content) > 5 else None
    except Exception:
        return None


def _handle_query(user_id: str, question: str):
    """MCP retrieval → qwen3:4b → structured template_cards."""
    # Step 1: MCP query for wiki context
    context = _mcp_query(question)
    if not context:
        _send_markdown(user_id, "知识库查询失败，请重试。")
        return

    # Step 2: qwen3:4b JSON structured output
    card_data = _call_llm_json(question, context)
    if not card_data or "cards" not in card_data:
        # Fallback: extract from raw MCP context
        wiki_dir = WIKI_ROOT / "wiki"
        if not wiki_dir.exists():
            _send_markdown(user_id, "知识库目录不存在")
            return
        # Quick keyword search as last resort
        keywords = question.lower().split()
        results = []
        for md in sorted(wiki_dir.rglob("*.md")):
            text = md.read_text()
            score = sum(1 for kw in keywords if kw in text.lower())
            score += sum(2 for kw in keywords if kw in str(md).lower())
            if score > 0:
                results.append((score, md.stem, text[:800]))
        results.sort(key=lambda x: x[0], reverse=True)
        if not results:
            _send_markdown(user_id, f"知识库中暂无「{question}」相关内容。")
            return
        top = results[0]
        _send_template_card(user_id,
            title=top[1], summary=_extract_first_meaningful_text(top[2]),
            details=_extract_kv_from_markdown(top[2]) or _extract_section_kv(top[2]),
            source_desc=top[1])
        return

    # Step 3: Send cards
    cards = card_data["cards"]
    top_page = _get_top_page_titles(question)
    for i, card in enumerate(cards[:8]):
        if i > 0:
            time.sleep(0.8)
        details = _normalize_details(card.get("details", []))
        summary = card.get("summary", "")
        if not summary:
            summary = _call_llm_short(f"{card.get('title', question)} 的核心信息",
                                       json.dumps(details, ensure_ascii=False))
        _send_template_card(user_id,
            title=card.get("title", question),
            summary=summary,
            details=details,
            source_desc=f"{top_page} ({i + 1}/{len(cards)})")

    # Supplementary markdown if content is rich
    overall = card_data.get("summary", "")
    if overall and len(overall) > 100:
        clean = _clean_markdown(overall)
        if len(clean) > 50:
            _send_markdown(user_id, clean)


def _get_top_page_titles(query: str) -> str:
    """Get matching page titles for citation."""
    wiki_dir = WIKI_ROOT / "wiki"
    if not wiki_dir.exists():
        return "知识库"
    keywords = query.lower().split()
    results = []
    for md in sorted(wiki_dir.rglob("*.md")):
        text = md.read_text()
        score = sum(1 for kw in keywords if kw in text.lower())
        if score > 0:
            title = md.stem
            if text.startswith("---"):
                end = text.find("---", 3)
                if end != -1:
                    for line in text[3:end].splitlines():
                        if line.startswith("title:"):
                            title = line.split(":", 1)[1].strip()
                            break
            results.append((score, title))
    results.sort(key=lambda x: x[0], reverse=True)
    return ", ".join(t for _, t in results[:5]) if results else "知识库"


def _call_llm_json(question: str, context: str) -> dict | None:
    """Call qwen3:4b to produce structured JSON for template_card."""
    import re
    try:
        body = json.dumps({
            "model": "qwen3:4b",
            "messages": [
                {"role": "system", "content": (
                    "Output ONLY valid JSON. No other text.\n"
                    "Format: {\"summary\":\"整体一句话概述\",\"cards\":[{\"title\":\"分类\",\"summary\":\"100-200字摘要\","
                    "\"details\":[[\"键\",\"值\"]]}]}\n"
                    "Rules:\n"
                    "- summary: one-sentence overall answer (Chinese, 50-100 chars).\n"
                    "- cards: split into 2-5 logical categories.\n"
                    "- Each card: title=category name, summary=key points (100-200 chars), details=3-8 key-value pairs.\n"
                    "- Use real data only. No placeholders. Group related facts.\n"
                    "- Always respond in Chinese."
                )},
                {"role": "user", "content": f"[Wiki]\n{context}\n\n[Q]\n{question}"},
            ],
            "stream": False,
            "options": {"num_predict": 2000, "temperature": 0.1},
        }).encode()

        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=body, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = json.loads(resp.read()).get("message", {}).get("content", "")
            if not content.strip():
                print("[wecom] LLM JSON: empty response", flush=True)
                return None
            # Save full LLM output for debugging
            try:
                with open("/tmp/llm_debug.txt", "w") as f:
                    f.write(content)
            except Exception:
                pass
            # Extract JSON from response
            content_clean = content.strip()
            # Remove markdown code blocks
            content_clean = re.sub(r"```(?:json)?\s*", "", content_clean)
            content_clean = re.sub(r"```", "", content_clean)
            content_clean = content_clean.strip()

            # Try brace-matching first
            start = content_clean.find("{")
            if start == -1:
                print(f"[wecom] no JSON in: {content[:150]}", flush=True)
                return None

            depth = 0
            json_str = None
            for i, ch in enumerate(content_clean[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        json_str = content_clean[start:i + 1]
                        break

            if json_str:
                # Try direct parse
                try:
                    parsed = json.loads(json_str)
                    print(f"[wecom] JSON OK, keys={list(parsed.keys())}", flush=True)
                    return parsed
                except json.JSONDecodeError:
                    pass

                # Fix common errors and retry
                fixed = re.sub(r",\s*([}\]])", r"\1", json_str)  # trailing commas
                fixed = re.sub(r"([{,])\s*([a-zA-Z_]+)\s*:", r'\1"\2":', fixed)  # unquoted keys
                try:
                    parsed = json.loads(fixed)
                    print(f"[wecom] JSON fixed OK", flush=True)
                    return parsed
                except json.JSONDecodeError as e:
                    print(f"[wecom] JSON unfixable: {e}", flush=True)

            print(f"[wecom] JSON parse failed, fallback", flush=True)
            return None
    except Exception as e:
        print(f"[wecom] LLM JSON failed: {e}", flush=True)
        return None


# ---- Routes ----

@app.route("/webhook", methods=["GET"])
def verify_url():
    signature = request.args.get("msg_signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")
    echostr = request.args.get("echostr", "")
    if not TOKEN:
        return jsonify({"error": "not configured"}), 500
    try:
        if _verify_signature(signature, timestamp, nonce, echostr):
            return _decrypt_msg(echostr)
        return jsonify({"error": "signature mismatch"}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/webhook", methods=["POST"])
def receive_message():
    signature = request.args.get("msg_signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")

    # Respond immediately to acknowledge receipt
    response = "", 200

    if not TOKEN:
        return response

    try:
        xml_body = request.data.decode("utf-8")
        root = ET.fromstring(xml_body)
        encrypted_elem = root.find("Encrypt")
        if encrypted_elem is None or encrypted_elem.text is None:
            return response

        plain_xml = _decrypt_msg(encrypted_elem.text)
        msg_root = ET.fromstring(plain_xml)
        msg_type = msg_root.findtext("MsgType", "text")
        user_id = msg_root.findtext("FromUserName", "")
        content = msg_root.findtext("Content", "") or msg_root.findtext("Text", "") or ""

        if user_id and content:
            # Process in background, don't block the response
            threading.Thread(target=_process, args=(user_id, content), daemon=True).start()

    except Exception:
        pass

    return response


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "configured": bool(TOKEN and AES_KEY and CORP_ID),
        "agent_ready": bool(SECRET and AGENT_ID),
        "wiki_root": str(WIKI_ROOT),
        "inbox_exists": RAW_INBOX.exists(),
    })


if __name__ == "__main__":
    configured = bool(TOKEN and AES_KEY and CORP_ID)
    print(f"[wecom-webhook] 启动 {HOST}:{PORT} | 回调: {configured} | 主动消息: {bool(SECRET and AGENT_ID)}", flush=True)
    app.run(host=HOST, port=PORT, debug=False)
