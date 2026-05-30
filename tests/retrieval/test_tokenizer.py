"""分词器单元测试."""

from knowledge_wiki.wiki.retrieval.tokenizer import remove_stopwords, tokenize


class TestTokenizer:
    """分词功能测试."""

    def test_search_mode_fine_grained(self):
        """搜索模式：细粒度切分，提高召回."""
        # 用 4 字或更长词测试 cut_for_search 的细粒度效果
        tokens = tokenize("前端代码规范测试", mode="search")
        assert len(tokens) >= 3, f"切分不够细: {tokens}"
        # 核心词应出现
        assert "前端" in tokens or "代码" in tokens or "规范" in tokens

    def test_index_mode_coarse(self):
        """索引模式：粗粒度切分，保留语义单元."""
        tokens = tokenize("渐进式披露", mode="index")
        assert "渐进式披露" in tokens or len(tokens) >= 2

    def test_mixed_cn_en(self):
        """中英混合分词."""
        tokens = tokenize("LLM Wiki 知识库", mode="search")
        assert "LLM" in tokens or "llm" in tokens
        assert "Wiki" in tokens or "wiki" in tokens

    def test_empty_text(self):
        """空文本返回空列表."""
        assert tokenize("", mode="search") == []

    def test_punctuation_filtered(self):
        """标点被过滤."""
        tokens = tokenize("你好，世界。", mode="search")
        assert "。" not in tokens
        assert "，" not in tokens


class TestStopwords:
    """停用词过滤测试."""

    def test_removes_question_words(self):
        """过滤中文疑问词."""
        tokens = ["什么", "是", "知识库", "怎么"]
        clean = remove_stopwords(tokens)
        assert "什么" not in clean
        assert "是" not in clean
        assert "怎么" not in clean
        assert "知识库" in clean

    def test_removes_english_stopwords(self):
        """过滤英文停用词."""
        tokens = ["the", "a", "knowledge", "wiki"]
        clean = remove_stopwords(tokens)
        assert "the" not in clean
        assert "a" not in clean
        assert "knowledge" in clean
        assert "wiki" in clean
