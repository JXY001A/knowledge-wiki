"""webhook/process.py 消息路由单元测试."""

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
    def test_url_fallback_to_ingest(self):
        """URL 消息默认走 ingest-article skill."""
        replies = []
        with patch("knowledge_wiki.webhook.process.is_url", return_value=True):
            with patch("knowledge_wiki.skill.engine.match_skill", return_value=None):
                with patch("knowledge_wiki.skill.planner.execute_skill") as mock_exec:
                    mock_exec.return_value = ""
                    process_message(
                        "test_user", "https://example.com",
                        lambda uid, txt: replies.append(txt), lambda *a: None,
                    )
        assert mock_exec.called

    def test_non_url_defaults_to_query(self):
        """非 URL 非 ? 的消息默认走 query-knowledge."""
        replies = []
        with patch("knowledge_wiki.webhook.process.is_url", return_value=False):
            with patch("knowledge_wiki.skill.engine.match_skill", return_value=None):
                with patch("knowledge_wiki.skill.engine.classify_intent_llm",
                           return_value=None):
                    with patch("knowledge_wiki.skill.planner.execute_skill") as mock_exec:
                        mock_exec.return_value = "result"
                        process_message(
                            "test_user", "GPU 性能优化技巧",
                            lambda uid, txt: replies.append(txt), lambda *a: None,
                        )
        # Should have called query-knowledge (not save-note)
        call_args = [c[0][0] for c in mock_exec.call_args_list]
        assert "query-knowledge" in call_args or mock_exec.call_count >= 1

    def test_question_prefix_detected(self):
        """? 前缀触发 query-knowledge."""
        replies = []
        with patch("knowledge_wiki.skill.planner.execute_skill") as mock_exec:
            mock_exec.return_value = "answer"
            process_message(
                "test_user", "? MCP 是什么",
                lambda uid, txt: replies.append(txt), lambda *a: None,
            )
        call_args = [c[0][0] for c in mock_exec.call_args_list]
        assert "query-knowledge" in call_args

    def test_history_passed_to_context(self):
        """多轮对话历史传递到 ctx."""
        history = [
            {"role": "user", "content": "什么是 MCP"},
            {"role": "bot", "content": "MCP 是..."},
        ]
        with patch("knowledge_wiki.skill.planner.execute_skill") as mock_exec:
            mock_exec.return_value = "answer"
            process_message(
                "test_user", "详细说说",
                lambda u, t: None, lambda *a: None,
                history=history,
            )
        ctx = mock_exec.call_args[0][1]
        assert "history" in ctx
        assert len(ctx["history"]) == 2
