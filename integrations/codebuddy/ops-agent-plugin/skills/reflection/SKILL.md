---
name: reflection
description: Reassess hypotheses after insufficient evidence or failed verification without controlling the workflow loop.
---

# Reflection

## Skill 目标

比较假设、证据和实验结果，决定保留、拒绝、补充哪些候选，并建议下一类动作；循环次数和实际跳转仍由 Runtime 控制。

## 适用场景

适用于证据为空或不足、实验失败、验证未确认，且 Runtime 发出 REFLECT 任务的场景。

## 输入 Contract

`ReflectionRequest`，包含 HypothesisSet、Evidence、ExperimentResult 列表和 iteration。

## 输出 Contract

`ReflectionResult`，包含摘要、保留/拒绝/新增假设、缺失证据、next_action 和 should_continue。

## 操作步骤

1. 对照每个假设的预期证据与实际证据。
2. 区分“被反驳”和“尚未验证”。
3. 检查失败是方法问题、工具问题还是假设问题。
4. 只提出一个受限 next_action。
5. 明确继续分析还需要什么信息。

## 可调用 MCP

只允许 `incident_get_state` 刷新权威状态；不得在 Reflection 内直接执行建议动作。

## 禁止行为

禁止自行循环、修改计数、直接采集证据或复现实验、把实验基础设施失败解释为假设被反驳。

## 退出条件

产生一个可执行 ReflectionResult，或判断没有合理的继续路径并设置 should_continue=false。

## 失败处理

信息不足时选择 COLLECT_EVIDENCE 并列明缺口；超过循环预算由 Runtime 进入 WAITING_HUMAN，Skill 不规避上限。

## 示例

首次 Investigation 返回空批次时保留 H1/H2/H3，补回四项 Missing Evidence，建议 COLLECT_EVIDENCE；Runtime 决定重新进入 Evidence Plan。
