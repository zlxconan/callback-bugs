---
name: evidence-planning
description: Turn each prioritized hypothesis and its missing evidence into a minimal, typed EvidencePlan.
---

# Evidence Planning

## Skill 目标

严格执行 Hypothesis → Missing Evidence → EvidenceRequest，形成最小、可执行、可判定完成的 EvidencePlan。

## 适用场景

适用于 Runtime 的 EVIDENCE_PLAN 任务，或 Reflection 要求补充证据时的重新规划。

## 输入 Contract

`EvidencePlanningRequest` 提供 ProblemContext、HypothesisSet 与已有 Evidence；逐个读取其中的 Hypothesis 和 missing_evidence。

## 输出 Contract

`EvidencePlan` 包含 objective、一个或多个 `EvidenceRequest` 和 completion_criteria。

## 操作步骤

1. 从最高优先级 Hypothesis 开始。
2. 对每项 Missing Evidence 写清支持或反驳哪个候选。
3. 选择最小的 evidence_type、查询范围和安全采集方式。
4. 构造带 H-xxx 关联、优先级和 required 标志的 EvidenceRequest。
5. 去除已有 Evidence 已满足的请求。
6. 定义可以机械判定的完成标准。

## 可调用 MCP

只允许 `incident_get_state` 获取最新快照。此 Skill 负责规划，不直接调用 trace/log/metric 等采集工具。

## 禁止行为

禁止在 EvidenceRequest 中预填结论、无限扩大时间范围、重复采集已有证据、直接调用 Investigation 实现或决定状态跳转。

## 退出条件

每个关键 Missing Evidence 已映射到最少一个 EvidenceRequest，或明确说明无法安全获取。

## 失败处理

无法确定来源时保留 required 请求并描述缺口；涉及敏感或高成本数据时请求 Runtime/人工决策，不绕过权限。

## 示例

H1 缺少“首次是否成功”和“响应是否超时”，分别生成日志 EvidenceRequest 与 Trace EvidenceRequest，而不是直接认定超时重试已发生。
