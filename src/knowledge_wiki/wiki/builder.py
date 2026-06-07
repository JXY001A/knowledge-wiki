"""Wiki 页面构建 — 资料摘要页、概念页生成."""

import json
from datetime import datetime
from pathlib import Path
from knowledge_wiki.config import settings
from knowledge_wiki.wiki.atomic import atomic_write


def build_source_page(data: dict, url: str) -> Path:
    """从 LLM 数据构建 wiki/资料摘要/ 页面并保存."""
    today = datetime.now().strftime("%Y-%m-%d")
    tags = [t for t in data.get("tags", []) if t and t != "null"]
    concepts = data.get("concepts", [])
    title = data.get("title", f"资料摘要：{data.get('domain', '未分类')}")

    page = f"""---
title: {title}
type: source
tags: {json.dumps(tags, ensure_ascii=False)}
created: {today}
updated: {today}
sources: []
confidence: medium
source_url: {url}
media: article
---

> {data.get("summary", "（摘要缺失）")}

## 核心要点

"""
    for p in data.get("key_points", []):
        if p and str(p) != "null":
            page += f"- {p}\n"

    notes = data.get("notes", "（暂无详细笔记）")
    quotes = data.get("quotes", "（暂无引用数据）")

    page += f"""
## 详细笔记

{notes}

## 引用与数据

{quotes}

## 相关

"""
    if concepts:
        for c in concepts:
            if isinstance(c, dict):
                name = c.get("name", "")
                if name:
                    page += f"- [[{name}]]\n"
            elif c and str(c) != "null":
                page += f"- [[{c}]]\n"

    related = data.get("related_pages", [])
    if related:
        for r in related:
            if r and str(r) != "null":
                page += f"- {r}\n"

    page += f"\n- [[Wiki 目录]]\n"

    dest = settings.wiki_root / "wiki" / "资料摘要"
    dest.mkdir(parents=True, exist_ok=True)
    safe_name = title.replace(":", "：").replace("/", "-")
    filepath = dest / f"{safe_name}.md"
    atomic_write(filepath, page)
    return filepath


def build_concept_page(concept: dict) -> Path | None:
    """为提取的概念创建 wiki/概念/ 页面（如不存在）."""
    name = concept.get("name", "")
    if not name:
        return None

    dest_dir = settings.wiki_root / "wiki" / "概念"
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = name.replace(":", "：").replace("/", "-")
    filepath = dest_dir / f"{safe_name}.md"

    if filepath.exists():
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    definition = concept.get("definition", "")
    importance = concept.get("importance", "")

    page = f"""---
title: {name}
type: concept
tags: [概念]
aliases: []
created: {today}
updated: {today}
sources: []
related_concepts: []
confidence: medium
---

> {definition}

## 是什么

{definition}

## 为什么重要

{importance}

## 相关

- [[Wiki 目录]]
"""
    atomic_write(filepath, page)
    return filepath


def extract_concept_names(concepts: list) -> list[str]:
    """从 string 或 dict 列表中提取概念名称."""
    names = []
    for c in concepts:
        if isinstance(c, dict):
            n = c.get("name", "")
            if n:
                names.append(n)
        elif c and str(c) != "null":
            names.append(str(c))
    return names
