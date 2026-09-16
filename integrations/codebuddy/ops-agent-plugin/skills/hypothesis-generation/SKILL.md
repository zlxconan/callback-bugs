---
name: hypothesis-generation
description: Generate prioritized, falsifiable hypotheses while separating facts, inferences, and assumptions.
---

# Hypothesis Generation

## Skill 目标

根据问题、版本知识和已有证据生成有限、可证伪且互有区分度的 HypothesisSet。

## 适用场景

适用于 Runtime 发出的 HYPOTHESIS 任务，以及 Reflection 明确要求补充新假设的场景。

## 输入 Contract

`HypothesisGenerationRequest`，包含 ProblemContext、ProductContext、KnowledgeContext、可选 TroubleshootingContext 与已有 Evidence。

## 输出 Contract

`HypothesisSet`；每个 Hypothesis 必须分开 fact、inference、assumption、confidence、支持/反驳/缺失证据和 status。

## 操作步骤

1. 提取已确认事实，不加入解释。
2. 为不同因果机制形成候选推断。
3. 显式列出每个候选成立所需假设。
4. 写出能支持或反驳候选的缺失证据。
5. 按证据一致性而非措辞可信度排序。

## 可调用 MCP

可只读调用 `incident_get_state` 获取权威快照；需要定位代码机制时可调用 `code_search`，结果必须作为 Evidence 引用。

## 禁止行为

禁止采集无关数据、执行实验、把 assumption 提升为 fact、只保留单一不可证伪结论或直接推进 Runtime。

## 退出条件

候选集合覆盖主要差异化原因，且每个候选都有明确 Missing Evidence 和优先级。

## 失败处理

上下文不足时降低 confidence 并列出缺口；无法形成可证伪候选时返回失败 TaskResult，由 Runtime 路由。

## 示例

重复订单候选包括：首次成功但响应延迟触发重试、前端重复点击、消息队列重复消费；三者需要不同时间线和执行主体证据。
