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

    # 流式聊天 API（SSE — Server-Sent Events）
    @app.route("/chat/stream", methods=["POST"])
    def chat_stream():
        """流式 SSE 端点 — 检索+LLM→逐 token 推送到前端.

        请求格式同 /chat: {"text": "...", "conversation_id": "..."}
        响应: text/event-stream
        """
        from flask import Response, stream_with_context
        from knowledge_wiki.webhook.process import is_url

        data = request.get_json()
        text = data.get("text", "").strip()
        conv_id = data.get("conversation_id", "")
        if not text:
            return jsonify({"error": "empty text"}), 400

        # 加载历史
        history = []
        if conv_id:
            try:
                from knowledge_wiki.assistant.db import get_db, init_schema
                conn = get_db()
                init_schema(conn)
                rows = conn.execute(
                    "SELECT role, content FROM conversation_messages "
                    "WHERE conv_id=? ORDER BY created_at DESC LIMIT 20",
                    [conv_id],
                ).fetchall()
                conn.close()
                history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
            except Exception:
                pass

        # URL 不流式 — 走同步路径
        if is_url(text):
            return jsonify({"reply": "URL 处理不支持流式，请使用普通 /chat 端点", "history": []})

        # 收集完整回复（用于保存到 DB）
        full_reply_parts = []

        def generate():
            """SSE 事件生成器."""
            import logging
            _log = logging.getLogger(__name__)

            try:
                # 0. 意图分类 + 检索（复用现有流程）
                question = text.strip()

                # 0.3 用户画像
                profile_text = ""
                try:
                    from knowledge_wiki.memory.profile import build_profile
                    p = build_profile()
                    if p.get("status") == "ok" and p.get("total", 0) >= 5:
                        domains = list(p.get("top_domains", {}).keys())[:3]
                        if domains:
                            profile_text = f"## 用户画像\n活跃领域：{', '.join(domains)}。\n\n"
                except Exception:
                    pass

                # 0.5 历史上下文
                history_text = ""
                if history:
                    parts = []
                    for m in history[-10:]:
                        role = "用户" if m.get("role") == "user" else "助手"
                        content = m.get("content", "")[:300]
                        parts.append(f"{role}：{content}")
                    history_text = "## 对话历史\n" + "\n".join(parts) + "\n\n"

                # 1. 检索
                from knowledge_wiki.wiki.retrieval.pipeline import run_pipeline_detailed
                result = run_pipeline_detailed(question)
                wiki_context = result["text"]
                has_relevant = result.get("has_relevant", True)

                # 2. 构建上下文（画像 + 历史 + wiki）
                full_context = profile_text + history_text + wiki_context
                max_ctx = min(len(full_context), 6000)

                # 3. 选择模型
                use_deepseek = len(wiki_context) >= 1000 and getattr(settings, "deepseek_api_key", None)

                if use_deepseek:
                    # DeepSeek 流式
                    from knowledge_wiki.llm.deepseek import stream_deepseek
                    messages = [
                        {"role": "system", "content": (
                            "你是个人知识库助手。基于提供的知识库资料回答用户问题。"
                            "用中文回答，200-500字。用[[页面名]]标注引用。"
                            "不要用表格，用##标题分段。"
                        )},
                        {"role": "user", "content": f"## 知识库\n{full_context[:max_ctx]}\n\n## 问题\n{question}"},
                    ]
                    chunks = stream_deepseek(
                        settings.deepseek_model_ingest, messages,
                        temperature=0.3, max_tokens=2048,
                    )
                else:
                    # Ollama 流式
                    from knowledge_wiki.llm.ollama import stream_ollama
                    messages = [
                        {"role": "system", "content": (
                            "用中文回答，详细但不过于啰嗦。用##标题分段。"
                            "用**粗体**强调关键术语。用-列表。"
                            "不要用表格和代码块。200-400字。只基于提供的资料。"
                        )},
                        {"role": "user", "content": f"[Wiki]\n{full_context[:max_ctx]}\n\n[Q]\n{question}"},
                    ]
                    chunks = stream_ollama(
                        settings.ollama_model_query, messages,
                        num_predict=1200, temperature=0.3,
                    )

                # 4. 逐 token 发送
                for chunk in chunks:
                    if chunk:
                        full_reply_parts.append(chunk)
                        yield f"data: {json.dumps({'token': chunk})}\n\n"

                yield f"data: {json.dumps({'done': True})}\n\n"

            except Exception as e:
                _log.warning("stream error: %s", e)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        def after_stream(response):
            """流完成后保存消息到 DB."""
            full_reply = "".join(full_reply_parts)
            if conv_id and full_reply:
                try:
                    from knowledge_wiki.assistant.db import get_db, init_schema
                    from knowledge_wiki.memory.models import uuid7, now_iso
                    conn = get_db()
                    init_schema(conn)
                    conn.execute(
                        "INSERT INTO conversation_messages (id,conv_id,role,content,created_at) VALUES (?,?,?,?,?)",
                        [uuid7(), conv_id, "user", text[:2000], now_iso()],
                    )
                    conn.execute(
                        "INSERT INTO conversation_messages (id,conv_id,role,content,created_at) VALUES (?,?,?,?,?)",
                        [uuid7(), conv_id, "bot", full_reply[:3000], now_iso()],
                    )
                    conn.execute(
                        "UPDATE conversations SET updated_at=?, channel='web' WHERE id=?",
                        [now_iso(), conv_id],
                    )
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
            return response

        resp = Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
        # 注册 after-request 回调（Flask 在响应完成时调用）
        resp.call_on_close(lambda: after_stream(None))
        return resp

    # 会话持久化 API
    @app.route("/chat/convs", methods=["GET"])
    def list_convs():
        """获取历史会话列表（所有渠道）."""
        from knowledge_wiki.assistant.db import get_db, init_schema
        conn = get_db()
        init_schema(conn)
        rows = conn.execute(
            "SELECT id, title, updated_at, COALESCE(channel, 'web') as channel FROM conversations "
            "ORDER BY updated_at DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return jsonify([
            {"id": r["id"], "title": r["title"],
             "updated_at": r["updated_at"],
             "channel": r["channel"]}
            for r in rows
        ])

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
            conn.execute("INSERT INTO conversations (id,title,user_id,channel,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                         [conv_id, title, "web_user", "web", now_iso(), now_iso()])

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
