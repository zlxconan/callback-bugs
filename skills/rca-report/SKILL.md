---
name: rca-report
description: Produce a structured, evidence-linked RCA without merging facts, inference, root cause, remediation, or unverified items.
---

# RCA Report

## Skill 目标

把已验证状态整理为可审计 RCAReport，严格区分已确认事实、推断、根因、最小复现条件、修复建议、未验证事项和证据链。

## 适用场景

适用于 Runtime 发出的 RCA 任务，或使用 finish command 完成已具备 RootCauseAssessment 的 Incident。

## 输入 Contract

`IncidentState` 中的 `RootCauseAssessment`、Evidence、ExperimentResult 与 `VerificationResult`；不得使用未提交的私有上下文替代权威状态。

## 输出 Contract

`RCAReport`，在任务模式下包装为成功 `TaskResult` 提交。

## 操作步骤

1. 从 EvidenceBackedClaim 提取 confirmed_facts。
2. 将因果解释保留在 inferences。
3. 只将已达验证标准的项写入 root_causes。
4. 从成功实验提炼最小复现条件。
5. 给出按优先级排序且有理由的修复建议。
6. 保留所有未验证项。
7. 为事实和根因构造显式 E-xxx → H-xxx 证据链。

## 可调用 MCP

`incident_get_state` 读取快照；任务模式用 `incident_submit`，显式完成模式可用 `incident_finish`。不得通过其他 MCP 补造缺失证据。

## 禁止行为

禁止把 inference 写成 fact、删除反例或未验证项、声称证据链之外的根因、在报告阶段执行修复，或自行标记 Runtime 已完成。

## 退出条件

报告通过 RCAReport Schema，所有根因有 Hypothesis/Evidence 引用，Runtime 接受提交或返回终态。

## 失败处理

证据链断裂或根因未确认时拒绝生成确定性 RCA；保留未验证项并提交结构化失败，让 Runtime 决定 Reflection 或人工介入。

## 示例

重复订单报告把“两次请求、首次成功、响应延迟、二次成功”列为事实，把“重试与非幂等共同致因”列为推断和根因，并给出幂等键修复及生产延迟来源未验证项。
