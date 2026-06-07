"""企业微信 Webhook Flask 应用 — 路由注册."""

import json
import threading
from xml.etree import ElementTree as ET

from flask import Flask, request, jsonify
from knowledge_wiki.config import settings
from knowledge_wiki.webhook.wechat.crypto import decrypt_msg, verify_signature
from knowledge_wiki.webhook.wechat.api import send_markdown, send_template_card
from knowledge_wiki.webhook.process import process_message


def create_app() -> Flask:
    """创建 Flask 应用并注册路由."""
    app = Flask(__name__)

    @app.route("/webhook", methods=["GET"])
    def verify_url():
        """企业微信回调 URL 验证."""
        sig = request.args.get("msg_signature", "")
        ts = request.args.get("timestamp", "")
        nonce = request.args.get("nonce", "")
        echostr = request.args.get("echostr", "")

        if not settings.wecom_token:
            return jsonify({"error": "not configured"}), 500

        try:
            if verify_signature(sig, ts, nonce, echostr):
                return decrypt_msg(echostr)
            return jsonify({"error": "signature mismatch"}), 403
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/webhook", methods=["POST"])
    def receive_message():
        """接收企业微信消息回调."""
        sig = request.args.get("msg_signature", "")
        ts = request.args.get("timestamp", "")
        nonce = request.args.get("nonce", "")

        response = "", 200

        if not settings.wecom_token:
            return response

        try:
            xml_body = request.data.decode("utf-8")
            root = ET.fromstring(xml_body)
            encrypted_elem = root.find("Encrypt")
            if encrypted_elem is None or encrypted_elem.text is None:
                return response

            plain_xml = decrypt_msg(encrypted_elem.text)
            msg_root = ET.fromstring(plain_xml)
            msg_type = msg_root.findtext("MsgType", "text")
            user_id = msg_root.findtext("FromUserName", "")
            content = msg_root.findtext("Content", "") or msg_root.findtext("Text", "") or ""

            if user_id and content:
                # 后台处理，不阻塞响应
                threading.Thread(
                    target=process_message,
                    args=(user_id, content, send_markdown, send_template_card),
                    daemon=True,
                ).start()

        except Exception:
            pass

        return response

    @app.route("/health", methods=["GET"])
    def health():
        """健康检查端点."""
        from knowledge_wiki.wiki.paths import RAW_INBOX

        return jsonify({
            "status": "ok",
            "configured": bool(settings.wecom_token and settings.wecom_aes_key and settings.wecom_corp_id),
            "agent_ready": bool(settings.wecom_secret and settings.wecom_agent_id),
            "wiki_root": str(settings.wiki_root),
            "inbox_exists": RAW_INBOX.exists(),
        })

    # 主页面
    @app.route("/", methods=["GET"])
    def index():
        """Web 端聊天入口."""
        from pathlib import Path
        html_path = Path(__file__).parent / "templates" / "index.html"
        return html_path.read_text(encoding="utf-8")

    # 聊天 API
    @app.route("/chat", methods=["POST"])
    def chat_api():
        """Web 端聊天 API — 复用 process_message 引擎."""
        from knowledge_wiki.webhook.process import process_message

        data = request.get_json()
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"reply": "请输入内容", "history": []})

        replies = []

        def collect_reply(uid, content):
            replies.append(content)

        def noop(*a, **kw):
            pass

        process_message("web_user", text, collect_reply, noop)

        return jsonify({
            "reply": replies[0] if replies else "处理完成",
            "history": [],
        })

    @app.route("/chat", methods=["GET"])
    def chat_page():
        """Web 端聊天界面."""
        from pathlib import Path
        html_path = Path(__file__).parent / "templates" / "chat.html"
        return html_path.read_text(encoding="utf-8")

    # 会话持久化 API
    @app.route("/chat/convs", methods=["GET"])
    def list_convs():
        """获取历史会话列表."""
        from knowledge_wiki.assistant.db import get_db, init_schema
        conn = get_db()
        init_schema(conn)
        rows = conn.execute(
            "SELECT id, title, updated_at FROM conversations "
            "WHERE user_id='web_user' ORDER BY updated_at DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return jsonify([{"id": r["id"], "title": r["title"], "updated_at": r["updated_at"]} for r in rows])

    @app.route("/chat/convs", methods=["POST"])
    def create_conv():
        """创建或更新会话."""
        from knowledge_wiki.assistant.db import get_db, init_schema
        from knowledge_wiki.memory.models import uuid7, now_iso
        data = request.get_json()
        conv_id = data.get("id") or uuid7()
        title = data.get("title", "新对话")[:50]
        messages = data.get("messages", [])

        conn = get_db()
        init_schema(conn)

        # Upsert conversation
        existing = conn.execute("SELECT id FROM conversations WHERE id=?", [conv_id]).fetchone()
        if existing:
            conn.execute("UPDATE conversations SET title=?, updated_at=? WHERE id=?", [title, now_iso(), conv_id])
        else:
            conn.execute("INSERT INTO conversations (id,title,user_id,created_at,updated_at) VALUES (?,?,?,?,?)",
                         [conv_id, title, "web_user", now_iso(), now_iso()])

        # Replace messages
        conn.execute("DELETE FROM conversation_messages WHERE conv_id=?", [conv_id])
        for m in messages:
            mid = uuid7()
            conn.execute("INSERT INTO conversation_messages (id,conv_id,role,content,created_at) VALUES (?,?,?,?,?)",
                         [mid, conv_id, m["role"], m["content"], m.get("time", now_iso())])

        conn.commit()
        conn.close()
        return jsonify({"id": conv_id, "ok": True})

    @app.route("/chat/convs/<conv_id>", methods=["GET"])
    def get_conv(conv_id):
        """获取单个会话的所有消息."""
        from knowledge_wiki.assistant.db import get_db, init_schema
        conn = get_db()
        init_schema(conn)
        conv = conn.execute("SELECT * FROM conversations WHERE id=?", [conv_id]).fetchone()
        if not conv:
            conn.close()
            return jsonify({"error": "not found"}), 404
        msgs = conn.execute(
            "SELECT role, content, created_at FROM conversation_messages WHERE conv_id=? ORDER BY created_at",
            [conv_id]
        ).fetchall()
        conn.close()
        return jsonify({
            "id": conv["id"], "title": conv["title"],
            "messages": [{"role": m["role"], "text": m["content"], "time": m["created_at"]} for m in msgs],
        })

    @app.route("/chat/convs/<conv_id>", methods=["DELETE"])
    def delete_conv(conv_id):
        """删除会话."""
        from knowledge_wiki.assistant.db import get_db, init_schema
        conn = get_db()
        init_schema(conn)
        conn.execute("DELETE FROM conversations WHERE id=?", [conv_id])
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    # 管理后台
    @app.route("/admin", methods=["GET"])
    def admin_dashboard():
        """管理后台仪表盘."""
        from pathlib import Path
        html_path = Path(__file__).parent / "templates" / "dashboard.html"
        return html_path.read_text(encoding="utf-8")

    @app.route("/admin/data", methods=["GET"])
    def admin_data():
        """仪表盘 JSON 数据."""
        from knowledge_wiki.webhook.admin import dashboard_data
        return jsonify(dashboard_data())

    return app
