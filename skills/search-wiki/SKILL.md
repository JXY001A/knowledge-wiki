# search-wiki

在 wiki 知识库中按关键词搜索，返回匹配页面列表和内容摘录。

## 触发条件

- 用户输入包含：搜索、查找、search、find、有哪些、找一下
- 或以 `? 搜索` 或 `? 查找` 开头

## 输入

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| input_text | string | ✅ | 搜索关键词或查询文本 |

## 输出

匹配页面列表，每项含标题、路径、正文摘录。

## 执行步骤

1. 从 input_text 提取搜索关键词
2. 调用 `wiki.search.search_wiki(keyword)` 检索
3. 格式化结果列表
4. 返回给用户

## 前置依赖

- `wiki.search.search_wiki()` — 关键字搜索
- `wiki.frontmatter.parse_frontmatter()` — 解析页面标题

## 评估标准

- 匹配准确率：搜索结果与关键词相关
- 响应速度：< 3s
