"""webhook/process.py 消息路由单元测试 — v5 LLM Router 架构."""

from unittest.mock import patch, MagicMock
from knowledge_wiki.webhook.process import (
    is_url, process_message,
)
from knowledge_wiki.evolve.gap_detector import _extract_gaps_from_text


class TestIsUrl:
    def test_http_url(self):
        assert is_url("https://example.com/article") is True

    def test_http_no_s(self):
        assert is_url("http://test.com") is True

    def test_not_url(self):
        assert is_url("这不是 URL") is False

    def test_url_mid_text(self):
        assert is_url("查看 https://example.com 这个") is False

    def test_empty(self):
        assert is_url("") is False


class TestProcessMessage:
    def test_url_routes_to_ingest(self):
        """URL 消息调用 _exec_ingest_url."""
        replies = []
        with patch("knowledge_wiki.webhook.process.is_url", return_value=True):
            with patch("knowledge_wiki.skill.tools._exec_ingest_url") as mock_ingest:
                mock_ingest.return_value = "已摄取"
                process_message(
                    "test_user", "https://example.com",
                    lambda uid, txt: replies.append(txt), lambda *a: None,
                )
        assert mock_ingest.called
        assert len(replies) > 0

    def test_question_prefix_queries_knowledge(self):
        """? 前缀强制知识查询."""
        replies = []
        with patch("knowledge_wiki.skill.tools._exec_search_knowledge") as mock_search:
            mock_search.return_value = "查询结果"
            process_message(
                "test_user", "? MCP 是什么",
                lambda uid, txt: replies.append(txt), lambda *a: None,
            )
        assert mock_search.called
        assert len(replies) > 0

    def test_normal_text_uses_router(self):
        """普通文本使用 LLM Router."""
        replies = []
        with patch("knowledge_wiki.skill.router.route_intent") as mock_route:
            mock_route.return_value = {"type": "chat", "reply": "你好！"}
            process_message(
                "test_user", "你好",
                lambda uid, txt: replies.append(txt), lambda *a: None,
            )
        assert mock_route.called
        mock_route.assert_called_once()
        args = mock_route.call_args[0]
        assert args[0] == "你好"  # first arg is text
        assert len(replies) > 0

    def test_history_passed_to_context(self):
        """多轮对话历史传递到 router context."""
        history = [
            {"role": "user", "content": "什么是 MCP"},
            {"role": "bot", "content": "MCP 是..."},
        ]
        with patch("knowledge_wiki.skill.router.route_intent") as mock_route:
            mock_route.return_value = {"type": "chat", "reply": "回答"}
            process_message(
                "test_user", "详细说说",
                lambda u, t: None, lambda *a: None,
                history=history,
            )
        ctx = mock_route.call_args[0][1]  # second arg is context
        assert "history" in ctx
        assert len(ctx["history"]) == 2
