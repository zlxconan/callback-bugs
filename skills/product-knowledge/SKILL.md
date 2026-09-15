---
name: product-knowledge
description: Resolve expected behavior for a specific product version, function, component, and dependency chain.
---

# Product Knowledge

## Skill 目标

建立当前问题对应的产品版本事实和预期行为，严格执行：产品 → 版本 → 功能 → 组件 → 依赖。

## 适用场景

适用于需要判断“当前产品、当前版本应如何工作”的 Knowledge Lookup 任务。

## 输入 Contract

`ProblemContext` 用于产品解析；`KnowledgeQuery` 携带问题、已解析 ProductContext 和查询意图。

## 输出 Contract

`ProductContext` 描述产品、版本、功能所在组件和配置；`KnowledgeContext` 返回版本适用事实、引用、Skill 标识和限制。

## 操作步骤

1. 从现象识别产品，无法确认时明确缺口。
2. 锁定发生问题的准确版本，不混用其他版本行为。
3. 找到受影响功能及其公开语义。
4. 映射到实现组件。
5. 识别影响该功能的上下游依赖与关键配置。
6. 只保留有来源且版本适用的事实。

## 可调用 MCP

`product_query`、`version_query`，均为只读。

## 禁止行为

禁止猜测版本、把通用文档当成当前版本事实、直接生成 Hypothesis、修改 Runtime 状态或调用写工具。

## 退出条件

已得到足以描述预期行为的 ProductContext 和 KnowledgeContext，或明确返回无法解析的知识限制。

## 失败处理

版本冲突时保留冲突引用并降低结论强度；查询失败应返回结构化错误，不用模型记忆填补产品事实。

## 示例

订单创建问题按 Order Service → 2026.09 → create order → order-api → client retry/idempotency dependency，得到“支持客户端重试、服务端未强制幂等”的版本知识。
