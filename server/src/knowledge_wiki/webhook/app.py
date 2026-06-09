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
    from pathlib import Path
    app = Flask(__name__, static_folder=None)

    # React 静态文件目录
    REACT_DIST = Path(__file__).parent.parent.parent.parent.parent / "web" / "build"

    def serve_react(path=""):
        """SPA fallback: 非 API 路径返回 React index.html."""
        from flask import send_from_directory
        if not (REACT_DIST / "index.html").exists():
            return "<h1>React build not found. Run: cd web && npm run build</h1>", 500
        return send_from_directory(str(REACT_DIST), "index.html")

    def serve_static(filename):
        """服务 React 静态资源."""
        from flask import send_from_directory
        assets = REACT_DIST / "assets"
        return send_from_directory(str(assets), filename)

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

    # 聊天 API
    @app.route("/chat", methods=["POST"])
    def chat_api():
        """Web 端聊天 API — 复用 process_message 引擎，支持多轮对话."""
        from knowledge_wiki.webhook.process import process_message, is_url

        data = request.get_json()
        text = data.get("text", "").strip()
        conv_id = data.get("conversation_id", "")
        if not text:
            return jsonify({"reply": "请输入内容", "history": []})

        # 加载历史对话（最近 10 轮）
        history = []
        if conv_id:
            try:
                from knowledge_wiki.assistant.db import get_db, init_schema
                conn = get_db()
                init_schema(conn)
                rows = conn.execute(
                    "SELECT role, content FROM conversation_messages "
                    "WHERE conv_id=? ORDER BY created_at DESC LIMIT 20",
                    [conv_id]
                ).fetchall()
                conn.close()
                history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
            except Exception:
                pass

        replies = []

        def collect_reply(uid, content):
            replies.append(content)

        def noop(*a, **kw):
            pass

        # URL 摄取耗时 30-60s, 后台线程处理
        if is_url(text):
            import threading
            threading.Thread(
                target=process_message,
                args=("web_user", text, collect_reply, noop),
                kwargs={"history": history},
                daemon=True,
            ).start()
            return jsonify({
                "reply": "正在提取并分析链接内容...\n\n处理完成后会显示结果（可发送新消息刷新查看）",
                "history": [],
            })

        process_message("web_user", text, collect_reply, noop, history=history)

        reply = replies[-1] if replies else "处理完成"

        # 保存用户消息 + 助手回复到 DB（多轮对话历史持久化）
        if conv_id and reply:
            try:
                from knowledge_wiki.assistant.db import get_db, init_schema
                from knowledge_wiki.memory.models import uuid7, now_iso
                conn = get_db()
                init_schema(conn)
                # 保存用户消息
                conn.execute(
                    "INSERT INTO conversation_messages (id,conv_id,role,content,created_at) VALUES (?,?,?,?,?)",
                    [uuid7(), conv_id, "user", text[:2000], now_iso()],
                )
                # 保存助手回复
                conn.execute(
                    "INSERT INTO conversation_messages (id,conv_id,role,content,created_at) VALUES (?,?,?,?,?)",
                    [uuid7(), conv_id, "bot", reply[:3000], now_iso()],
                )
                # 更新会话时间
                conn.execute(
                    "UPDATE conversations SET updated_at=? WHERE id=?",
                    [now_iso(), conv_id],
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

        return jsonify({
            "reply": reply,
            "history": [],
        })

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

    @app.route("/admin/data", methods=["GET"])
    def admin_data():
        """仪表盘 JSON 数据."""
        from knowledge_wiki.webhook.dashboard import dashboard_data
        return jsonify(dashboard_data())

    # React SPA — / + /chat + /admin + /status 返回 React
    _spa_routes = ["/", "/chat", "/admin", "/status"]
    for r in _spa_routes:
        app.add_url_rule(r, f"spa_{r}", serve_react)

    # React 静态资源
    @app.route("/assets/<filename>", methods=["GET"])
    def react_assets(filename):
        return serve_static(filename)

    return app
