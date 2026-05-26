---
title: 资料摘要：C端AIGC内容自优化实践
type: source
tags: ["智能体", "架构", "最佳实践", "案例", "范式"]
created: 2026-05-26
updated: 2026-05-26
sources: []
confidence: medium
source_url: https://mp.weixin.qq.com/s/2-bum4w_6xWAnc82fvk-3A
media: article
---

> 本文介绍蚂蚁保保险快查深度解读页面生成系统(DIPG)，核心思想是摒弃LLM实时生成直出C端，改用离线预生成+验证闭环的Harness Engineering模式。系统由Host、Research、Verify三个Agent协作，通过程序化结构校验与LLM事实校验两层把关，并结合精准修正与prompt回灌机制，确保只有合格HTML交付用户。最终形成线下迭代verify能力→线上离线把关主交付→实时兜底的三级反馈回路，实现内容生产质量的持续演进。

## 核心要点

- C端AIGC不宜实时生成直出，应离线预生成+验证后存储交付，保证秒出与内容质量
- DIPG由Host/Research/Verify三个Agent协作，通过LangGraph三层嵌套实现离线闭环
- Verify Agent采用程序化HTML校验与LLM事实校验双层架构，依赖/audit/审计通道做数据对齐
- Host Agent按fix_hint精准修补HTML，而非重派Research，实现高效收敛与低风险修正
- 高频错误通过半自动提炼回灌至生成prompt，实现系统持续自优化
- 整体形成三级Harness嵌套：线下迭代verify、线上离线主交付、实时兜底共用prompt基础

## 详细笔记

## 背景
蚂蚁保保险快查的深度解读页面需要为用户展示一份几千字的HTML解读报告。若采用传统模式，用户点击时实时调用LLM生成，会面临两大问题：
- **时延**：完整Agent流程需检索素材、阅读条款、网络搜索并生成HTML，推理耗时数十秒，无法满足C端“秒开”要求。
- **质量**：LLM生成HTML容易出现渲染类错误（如孤儿闭合标签导致页面塌陷）和幻觉类错误（如编造“优于市场85%”这类无数据支撑的表述），无法100%可靠。

因此，DIPG将架构翻转，采用 **离线生成 + Harness把关 + DB按品开启 + C端直出** 的模式。实时生成降级为未开启品的兜底路径，确保用户看到的每一份HTML都经过校验。

## 两条线上链路
- **离线链路（主路径）**：Host Agent调度Research Agent生成初版，再提交Verify Agent校验，通过fix_hint持续修正直至通过，最终通过callback将合格HTML刷入DB。用户请求时直接从DB读取，命中率100%。
- **实时链路（兜底）**：仅运行Research Agent，不经过Verify，产物不经校验直接返回，仅在品未开启时触发。两条链路的Research Agent完全同源，共享Prompt与代码。

## 三个Agent的分工
系统内部由三个基于LangGraph的Agent协作，分工明确：
- **Host Agent**：总编排与精准修正。按照“研究→校验→修正→再校验”的流程派活。当Verify返回修正意见时，Host Agent自己调`edit_file`/`write_file`在已有HTML上做局部Patch，**绝不重派Research Agent**，避免全盘重写。
- **Research Agent**：从零生成HTML。调用`download_insurance_product_materials`、`read_disk_file`、`web_search`工具，基于前置溯源注释规则生成报告并写入`state["files"]["report.html"]`。
- **Verify Agent**：仅负责校验，不改HTML。内部由两个节点串行：`structural_check`（纯Python程序化校验，毫秒级，检查HTML闭合、层级等确定性规则）和`llm_verify`（LLM事实对齐校验，读取`/audit/`中的原始数据供给与HTML对比）。

Agent间通过`task`工具调用实现上下文隔离，共享数据通过`state["files"]`虚拟文件系统与`/audit/`审计目录传递。

## 关键设计
1. **Prompt契约**：Research Agent的提示词包含合规硬约束、8条事实保证规则、强制前置溯源注释等，从源头减少错误。规则不仅来自合规要求，更大量源自Verify Agent反复捕获的高频错误。
2. **双层校验**：程序化校验处理确定性结构问题（如闭合标签、样式标签），LLM事实校验专门对HTML数值与`/audit/`中的原始数据进行对齐，避免“无中生有”。两者分工，零假阳性且Token高效。
3. **精准修正策略**：由于Verify给出的fix_hint已精确定位（模块名、证据、建议替换内容），Host Agent只需执行轻量编辑，避免重生成带来的风险与成本，且循环收敛快（通常在1~3轮内完成）。
4. **Prompt回灌**：半自动将高频错误模式（如实体对齐错误、盲目对比）提炼为通用规则写回Research Agent提示词，使系统具备持续演进性。
5. **三级Harness嵌套**：Level 1 实时兜底、Level 2 离线主交付、Level 3 线下迭代Verify能力，三层共享同一套Research Prompt与/audit/数据契约，形成长期优化飞轮。

## 经验总结
- C端AIGC应默认离线预生成+验证+持久化，实时仅作兜底。
- 离线链路的所有改进（Prompt升级、规则新增）必须通过代码/提示同源同步给实时链路。
- 能用确定性程序判定的（HTML结构）绝不交给LLM。
- 事实性校验必须有审计通道，对照原始数据供给。

## 引用与数据

- “C 端 AIGC 交付的本质要求是:用户点开那一刻看到的 HTML,必须是已经被校验过的。”
- “一次完整的深度解读需要 agentic 检索素材与条款、生成几千字 HTML,LLM 推理加起来几十秒。C 端用户等不起,‘秒出’是基础体验要求。”
- “思路很简单,但概念上需要翻转: C 端 AIGC 不应该把‘实时生成给用户’作为默认假设。默认假设应该是‘离线生成 → Harness 把关 → 持久化产物给用户’,实时只作为兜底。”
- “Verify Agent 不只是质检员,它同时在替 Research Agent 的 prompt 产出训练信号。”
- “HelixVerify 告诉我们 AI 可以自举到自主迭代。DIPG 在这个基础上更进一步: AI 实时生成的产物,可以因为一条带 verify 闭环的离线主路径,变得 C 端可交付。”

## 相关

- [[Harness Engineering]]
- [[Verify Agent]]
- [[/audit/ 审计通道]]
- [[Prompt 回灌]]
- [[离线主路径 + 实时兜底]]
- [[Harness Engineering: 为AI打造可持续迭代环境的实践]]
- [[LangGraph 多Agent协作模式]]
- [[LLM事实性校验方法]]
- [[AIGC内容生产系统设计]]

- [[Wiki 目录]]
