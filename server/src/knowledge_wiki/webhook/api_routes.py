"""REST API 蓝图 — 知识库、待办、语音等专属端点.

通过 register_api_routes(app) 挂载到 Flask 应用。
"""
import json
import logging
from datetime import datetime

from flask import request, jsonify

from knowledge_wiki.config import settings
from knowledge_wiki.assistant.db import get_db, init_schema

_log = logging.getLogger(__name__)


def register_api_routes(app):
    """将所有 REST API 路由注册到 Flask app."""

    # =====================================================================
    # Wiki 页面
    # =====================================================================

    @app.route("/api/wiki/page", methods=["GET"])
    def wiki_page_detail():
        """获取单个 wiki 页面完整内容.

        Query: ?path=wiki/概念/xxx.md 或 ?title=页面标题
        """
        path = request.args.get("path", "")
        title = request.args.get("title", "")

        if not path and not title:
            return jsonify({"error": "provide 'path' or 'title' parameter"}), 400

        from knowledge_wiki.wiki.paths import find_page_path

        if path:
            page = _get_page_content(path)
        else:
            resolved = find_page_path(title)
            if not resolved:
                return jsonify({"error": "page not found"}), 404
            page = _get_page_content(resolved)

        if not page:
            return jsonify({"error": "page not found"}), 404

        return jsonify(page)

    # =====================================================================
    # 待办管理
    # =====================================================================

    @app.route("/api/todos", methods=["GET"])
    def list_todos():
        """列出待办.

        Query: ?status=pending|done|cancelled|all
        """
        status = request.args.get("status", "")
        conn = get_db()
        init_schema(conn)

        if status and status != "all":
            rows = conn.execute(
                "SELECT * FROM todos WHERE status=? ORDER BY "
                "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
                "created_at DESC LIMIT 50",
                [status],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM todos ORDER BY "
                "CASE status WHEN 'pending' THEN 0 WHEN 'done' THEN 1 ELSE 2 END, "
                "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
                "created_at DESC LIMIT 50"
            ).fetchall()
        conn.close()

        return jsonify({"todos": [dict(r) for r in rows]})

    @app.route("/api/todos", methods=["POST"])
    def create_todo():
        """创建待办.

        Body: {"title": "买牛奶", "priority": "high", "deadline": "2026-06-11"}
        """
        data = request.get_json()
        title = (data.get("title", "") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400

        from knowledge_wiki.assistant.models import Todo
        from knowledge_wiki.memory.models import uuid7, now_iso

        t = Todo(
            title=title[:80],
            priority=data.get("priority", "medium"),
            deadline=data.get("deadline"),
            tags=data.get("tags", []),
            source="web_admin",
        )
        d = t.to_dict()
        # 覆盖 id/created_at 使用 server-side 生成
        d["id"] = uuid7()
        d["created_at"] = now_iso()
        d["updated_at"] = now_iso()

        cols = ", ".join(d.keys())
        ph = ", ".join("?" for _ in d)

        conn = get_db()
        init_schema(conn)
        conn.execute(f"INSERT INTO todos ({cols}) VALUES ({ph})", list(d.values()))
        conn.commit()
        conn.close()

        return jsonify({"id": d["id"], "ok": True}), 201

    @app.route("/api/todos/<todo_id>", methods=["PATCH"])
    def update_todo(todo_id):
        """更新待办.

        Body: {"status": "done"} 或 {"priority": "high", "title": "新标题"}
        """
        data = request.get_json()
        conn = get_db()
        init_schema(conn)

        existing = conn.execute("SELECT * FROM todos WHERE id=?", [todo_id]).fetchone()
        if not existing:
            conn.close()
            return jsonify({"error": "not found"}), 404

        allowed = {"status", "priority", "title", "deadline"}
        updates = []
        values = []
        for key, val in data.items():
            if key in allowed:
                updates.append(f"{key}=?")
                values.append(val)

        if data.get("status") == "done":
            updates.append("completed_at=?")
            values.append(datetime.now().isoformat())

        if updates:
            from knowledge_wiki.memory.models import now_iso
            updates.append("updated_at=?")
            values.append(now_iso())
            values.append(todo_id)
            conn.execute(
                f"UPDATE todos SET {', '.join(updates)} WHERE id=?",
                values,
            )
            conn.commit()

        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/todos/<todo_id>", methods=["DELETE"])
    def delete_todo(todo_id):
        """软删除待办（status=cancelled）."""
        from knowledge_wiki.memory.models import now_iso

        conn = get_db()
        init_schema(conn)
        conn.execute(
            "UPDATE todos SET status='cancelled', updated_at=? WHERE id=?",
            [now_iso(), todo_id],
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    # =====================================================================
    # 知识检索（拆解自 /chat）
    # =====================================================================

    @app.route("/api/knowledge/search", methods=["POST"])
    def knowledge_search():
        """专属知识检索.

        Body: {"query": "DeepSeek 模型", "top_n": 5}
        """
        data = request.get_json()
        query = (data.get("query", "") or "").strip()
        if not query:
            return jsonify({"error": "query is required"}), 400

        top_n = data.get("top_n", 5)

        from knowledge_wiki.wiki.retrieval.pipeline import run_pipeline_detailed
        result = run_pipeline_detailed(query)

        # 从上下文中提取 wikilinks 作为结构化结果
        from knowledge_wiki.wiki.search import extract_wikilinks
        wikilinks = extract_wikilinks(result["text"])
        seen = set()
        results = []
        for link in wikilinks:
            if link not in seen and len(results) < top_n:
                seen.add(link)
                results.append({
                    "title": link,
                    "path": f"wiki/{link}.md",
                    "score": 1.0,
                    "source": "retrieval",
                })

        return jsonify({
            "results": results,
            "context": result["text"],
            "has_relevant": result.get("has_relevant", True),
        })

    # =====================================================================
    # 工具/操作执行（拆解自 /chat）
    # =====================================================================

    @app.route("/api/action/execute", methods=["POST"])
    def execute_action():
        """执行指定工具.

        Body: {"tool": "manage_todos", "args": {"action": "list"}}
        """
        data = request.get_json()
        tool = (data.get("tool", "") or "").strip()
        args = data.get("args", {})

        if not tool:
            return jsonify({"error": "tool name is required"}), 400

        from knowledge_wiki.skill.tools import execute_tool, TOOLS
        valid_names = {t["function"]["name"] for t in TOOLS}
        if tool not in valid_names:
            return jsonify({"error": f"unknown tool: {tool}"}), 400

        ctx = {
            "user_id": "web_user",
            "send_md": lambda uid, msg: None,
            "send_tpl": lambda *a, **kw: None,
            "history": [],
        }

        try:
            result_text = execute_tool(tool, args, ctx)
            return jsonify({"reply": result_text, "success": True})
        except Exception as e:
            _log.warning("Tool %s failed: %s", tool, e)
            return jsonify({"reply": str(e), "success": False}), 500

    # =====================================================================
    # 语音助手 "若愚"
    # =====================================================================

    @app.route("/api/voice", methods=["POST"])
    def voice_process():
        """语音指令处理 —— 唯一触发 USB 音响播放的端点.

        Body: {"text": "查看今天的待办", "conversation_id": "..."}

        仅在语音唤醒路径下调用，文字输入不走此端点。
        """
        data = request.get_json(force=True)
        text = (data.get("text", "") or "").strip()
        conv_id = data.get("conversation_id", "")

        if not text:
            return jsonify({"error": "no text provided"}), 400

        # 加载对话历史
        history = []
        if conv_id:
            try:
                conn = get_db()
                init_schema(conn)
                rows = conn.execute(
                    "SELECT role, content FROM conversation_messages "
                    "WHERE conv_id=? ORDER BY created_at DESC LIMIT 20",
                    [conv_id],
                ).fetchall()
                conn.close()
                history = [
                    {"role": r["role"], "content": r["content"]}
                    for r in reversed(rows)
                ]
            except Exception:
                pass

        ctx = {
            "user_id": "voice_user",
            "input_text": text,
            "send_md": lambda uid, msg: None,
            "send_tpl": lambda *a, **kw: None,
            "history": history,
        }

        # 路由 + 执行
        from knowledge_wiki.skill.router import route_intent
        result = route_intent(text, ctx)
        reply = result.get("reply", "")

        # 通过 USB 音响播放
        spoken = False
        if reply and settings.voice_enabled:
            try:
                _speak_text(reply)
                spoken = True
            except Exception as e:
                _log.warning("TTS failed: %s", e)

        # 保存对话
        if conv_id and reply:
            try:
                from knowledge_wiki.memory.models import uuid7, now_iso
                conn = get_db()
                init_schema(conn)
                conn.execute(
                    "INSERT INTO conversation_messages (id,conv_id,role,content,created_at) "
                    "VALUES (?,?,?,?,?)",
                    [uuid7(), conv_id, "user", text[:2000], now_iso()],
                )
                conn.execute(
                    "INSERT INTO conversation_messages (id,conv_id,role,content,created_at) "
                    "VALUES (?,?,?,?,?)",
                    [uuid7(), conv_id, "bot", reply[:3000], now_iso()],
                )
                conn.execute(
                    "UPDATE conversations SET updated_at=?, channel='voice' WHERE id=?",
                    [now_iso(), conv_id],
                )
                conn.commit()
                conn.close()
            except Exception as e:
                _log.warning("Voice conv save failed: %s", e)

        return jsonify({"reply": reply, "spoken": spoken})


# =========================================================================
# 内部辅助
# =========================================================================

def _get_page_content(relative_path: str) -> dict | None:
    """读取 wiki 页面内容.

    Args:
        relative_path: 相对于 wiki_root 的路径，如 "wiki/概念/xxx.md"

    Returns:
        {path, title, frontmatter, content, size_lines, updated} 或 None
    """
    from knowledge_wiki.wiki.frontmatter import parse_frontmatter, strip_frontmatter

    full_path = settings.wiki_root / relative_path
    if not full_path.exists() or not full_path.is_file():
        return None

    text = full_path.read_text()
    fm = parse_frontmatter(full_path) if text.startswith("---") else {}
    body = strip_frontmatter(text) if text.startswith("---") else text

    return {
        "path": relative_path,
        "title": fm.get("title", full_path.stem) if fm else full_path.stem,
        "frontmatter": fm or {},
        "content": body,
        "size_lines": len(text.splitlines()),
        "updated": fm.get("updated", "") if fm else "",
    }


def _speak_text(text: str):
    """通过 USB 音响朗读文字（edge-tts → mpg123 → aplay）."""
    import asyncio
    import subprocess

    async def _gen():
        import edge_tts
        communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        await communicate.save("/tmp/voice-reply.mp3")

    asyncio.run(_gen())
    subprocess.run(
        ["mpg123", "-q", "-w", "/tmp/voice-reply.wav", "/tmp/voice-reply.mp3"],
        timeout=30,
    )
    subprocess.run(
        ["aplay", "-q", "-D", settings.tts_speaker_device, "/tmp/voice-reply.wav"],
        timeout=30,
    )
