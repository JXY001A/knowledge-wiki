"""企业微信主动消息 API — access_token、markdown、template_card."""

import json
import threading
import time
import urllib.request
import urllib.error
from knowledge_wiki.config import settings

# ---- Token 缓存 ----
_token_cache: dict = {"token": "", "expires": 0}
_token_lock = threading.Lock()


def get_access_token() -> str:
    """获取并缓存企业微信 API access_token."""
    global _token_cache
    now = time.time()
    with _token_lock:
        if _token_cache["token"] and _token_cache["expires"] > now + 60:
            return _token_cache["token"]

    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={settings.wecom_corp_id}&corpsecret={settings.wecom_secret}"
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


def send_markdown(user_id: str, content: str) -> bool:
    """向用户发送 markdown 消息."""
    token = get_access_token()
    if not token:
        return False

    body = json.dumps({
        "touser": user_id,
        "msgtype": "markdown",
        "agentid": int(settings.wecom_agent_id),
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


def send_template_card(user_id: str, title: str, summary: str,
                       details: list[tuple[str, str]] | None = None,
                       jump_title: str = "", jump_url: str = "",
                       source_desc: str = "知识库") -> bool:
    """向用户发送 template_card (text_notice) 消息."""
    token = get_access_token()
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

    if jump_title and jump_url:
        card["jump_list"] = [{"type": 1, "url": jump_url, "title": jump_title}]
        card["card_action"] = {"type": 1, "url": jump_url}
    else:
        card["card_action"] = {"type": 1, "url": "https://work.weixin.qq.com"}

    body = json.dumps({
        "touser": user_id,
        "msgtype": "template_card",
        "agentid": int(settings.wecom_agent_id),
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
