"""BM25 索引与搜索单元测试."""

from knowledge_wiki.wiki.retrieval.bm25 import bm25_search, build_bm25_index
from knowledge_wiki.wiki.retrieval.index_store import index_is_fresh, load_index, save_index


class TestBM25Build:
    """索引构建测试."""

    def test_all_docs_have_meta(self):
        """所有文档都有元数据映射."""
        index = build_bm25_index()
        for doc_id in range(index.num_docs):
            assert doc_id in index.doc_meta, f"doc_id {doc_id} 不在 doc_meta 中"
            assert index.doc_meta[doc_id].doc_id == doc_id

    def test_title_mapping(self):
        """标题→ID 反向映射完整."""
        index = build_bm25_index()
        for doc_id, meta in index.doc_meta.items():
            assert meta.title in index.title_to_id
            assert index.title_to_id[meta.title] == doc_id


class TestBM25Search:
    """搜索测试."""

    def test_returns_results(self):
        """查询返回结果."""
        index = build_bm25_index()
        results = bm25_search(index, "DeepSeek", candidates=None, top_n=3)
        assert len(results) > 0
        assert all(r.score > 0 for r in results)

    def test_candidates_filter(self):
        """候选集过滤有效."""
        index = build_bm25_index()
        # 只有一个候选
        candidates = ["DeepSeek"]
        results = bm25_search(index, "DeepSeek", candidates=candidates, top_n=5)
        assert all(r.title == "DeepSeek" for r in results)

    def test_top_n_respected(self):
        """top_n 限定生效."""
        index = build_bm25_index()
        results = bm25_search(index, "wiki", candidates=None, top_n=3)
        assert len(results) <= 3

    def test_field_scores_present(self):
        """field_scores 调试信息存在."""
        index = build_bm25_index()
        results = bm25_search(index, "AI", candidates=None, top_n=2)
        for r in results:
            assert "title" in r.field_scores
            assert "tags" in r.field_scores
            assert "body" in r.field_scores


class TestIndexStore:
    """索引序列化测试."""

    def test_save_and_load_roundtrip(self):
        """保存后加载往返一致."""
        index = build_bm25_index()
        save_index(index)
        loaded = load_index()
        assert loaded is not None
        assert loaded.num_docs == index.num_docs
        assert loaded.version == index.version

    def test_freshness_check(self):
        """索引新鲜度检查."""
        index = build_bm25_index()
        assert index_is_fresh(index) is True

    def test_load_nonexistent(self):
        """不存在的文件返回 None."""
        loaded = load_index(Path("/tmp/nonexistent_bm25.pkl.zst"))
        assert loaded is None


from pathlib import Path
