---
title: mermaid-test
---

## Test 1: basic
\`\`\`mermaid
flowchart TD
    A[hello] --> B[world]
\`\`\`

## Test 2: numbered
\`\`\`mermaid
flowchart TD
    A[1 hello] --> B[2 world]
\`\`\`

## Test 3: dot-space
\`\`\`mermaid
flowchart TD
    A[1. hello] --> B[2. world]
\`\`\`

## Test 4: paren-number
\`\`\`mermaid
flowchart TD
    A[1) hello] --> B[2) world]
\`\`\`

## Test 5: colon
\`\`\`mermaid
flowchart TD
    A[hello: world] --> B[test: foo]
\`\`\`

## Test 6: underscore
\`\`\`mermaid
flowchart TD
    A[hello_world] --> B[foo_bar]
\`\`\`

## Test 7: long label
\`\`\`mermaid
flowchart TD
    A[hello 这是] --> B[a very long label with many words in it for testing purposes]
\`\`\`

## Test 8: diamond
\`\`\`mermaid
flowchart TD
    A[hello] --> B{world?}
    B -->|yes| C[ok]
\`\`\`

## Test 9: pipe in label
\`\`\`mermaid
flowchart TD
    A[hello | world] --> B[foo | bar]
\`\`\`

## Test 10: combo
\`\`\`mermaid
flowchart TD
    A["1) 通知：正在提取"] --> B["2) fetch_url: GET 下载"] --> C{"3) 下载成功?"}
    C -->|yes| D["保存原文"]
\`\`\`
