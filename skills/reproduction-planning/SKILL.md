---
name: reproduction-planning
description: Turn one evidence-supported hypothesis into a minimal, safe, and verifiable experiment plan.
---

# Reproduction Planning

## Skill 目标

严格执行 Hypothesis → ExperimentPlan，把待验证因果机制转换成最小复现条件、步骤、成功标准、风险和回滚方案。

## 适用场景

适用于 Runtime 的 EXPERIMENT_PLAN 任务，且目标 Hypothesis 已有足够证据值得实验验证。

## 输入 Contract

`ExperimentPlanningRequest`，包含 ProblemContext、ProductContext、单个目标 Hypothesis 和 Evidence。

## 输出 Contract

`ExperimentPlan`，包含 objective、hypothesis_ids、environment、steps、success_criteria、rollback_steps、risk_level 和 requires_approval。

## 操作步骤

1. 选定一个可证伪 Hypothesis。
2. 提取触发机制和最小环境依赖。
3. 固定无关变量，写出顺序明确的 ExperimentStep。
4. 定义能确认或反驳假设的可观察成功标准。
5. 评估副作用、权限和是否需要审批。
6. 在执行前写出可靠回滚步骤。

## 可调用 MCP

可只读调用 `incident_get_state`、`code_search`、`call_graph` 补充规划依据。不得在规划阶段调用 reproduction-mcp 写工具。

## 禁止行为

禁止直接执行实验、隐式故障注入、忽略回滚、把生产环境作为默认实验环境或把多个因果假设混入一个不可判定实验。

## 退出条件

ExperimentPlan 可以由独立执行者照单执行并明确判断成功/失败，或因风险无法接受而请求人工处理。

## 失败处理

环境或回滚不可定义时不生成可执行计划；标明缺口并返回失败或人工介入建议，由 Runtime 路由。

## 示例

对 H1 设置相同业务标识，令首次响应延迟超过客户端超时，允许一次重试；成功标准是出现两个订单且时间线符合首次成功、超时、重试、二次创建。
