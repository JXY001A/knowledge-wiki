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
