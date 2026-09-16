---
name: incident-analysis
description: Complete Runtime-assigned incident analysis tasks while leaving workflow state and transitions to Core Runtime.
---

# Incident Analysis

## Skill 目标

把用户问题提交给 Runtime，逐个完成 RuntimeTask，并以可审计的 TaskResult 推进到 RCA、等待人工、失败或完成。Skill 只定义分析方法，不拥有状态机。

## 适用场景

适用于从 ProblemContext 开始的完整线上问题分析、证据获取、受控复现和 RCA 会话。

## 输入 Contract

`StartIncidentRequest` 用于开始；后续每轮只处理 `RuntimeTask` 及 `incident_get_state` 返回的 `IncidentState`。

## 输出 Contract

每个任务输出一个 `TaskResult`；终态可读取 `RCAReport`。

## 操作步骤

1. 使用 `incident_start` 建立 Incident，不自行构造中间状态。
2. 循环调用 `incident_next`，只执行返回任务指定的职责。
3. 使用对应 Canonical Skill 和获准 MCP 形成强类型结果。
4. 通过 `incident_submit` 提交结果，再由 Runtime 决定下一 Stage。
5. 到达 completed、failed 或 waiting_human 时退出或等待明确输入。

## 可调用 MCP

`incident_start`、`incident_next`、`incident_submit`、`incident_get_state`、`incident_finish`。其他 MCP 只能在当前 RuntimeTask 与专项 Skill 允许时调用。

## 禁止行为

禁止自行修改 IncidentState、跳过 RuntimeTask、无限循环、把推断写成事实、绕过审批或让 Skill 决定状态转换。

## 退出条件

Runtime 返回 completed、failed、waiting_human，或 `incident_next` 返回空且状态已终止。

## 失败处理

将工具或推理失败转换成带 ErrorResponse 的失败 TaskResult。retryable 必须反映真实可重试性；是否重试由 Runtime 决定。

## 示例

创建订单首次成功但响应超时：开始 Incident，领取 Knowledge/Hypothesis/Evidence/Experiment/RCA 任务，逐项提交，最终读取包含 H1 证据链的 RCAReport。
