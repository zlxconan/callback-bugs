---
name: troubleshooting
description: Select version-specific troubleshooting operations without executing or orchestrating them.
---

# Troubleshooting

## Skill 目标

按产品 → 版本 → 故障 → 现象 → 原因 → 操作 → 验证组织排障知识，输出可供 Agent 选择的方法与约束。

## 适用场景

适用于已知产品和版本，需要查找已知故障模式、检查步骤、规避方案与验证标准的任务。

## 输入 Contract

`KnowledgeQuery`，必须包含问题上下文和尽可能准确的 ProductContext。

## 输出 Contract

`TroubleshootingContext`，分别保存已执行操作、观察结果、已知 workaround 和约束。

## 操作步骤

1. 确认产品与版本。
2. 将故障类别与实际现象匹配，不以关键词替代证据。
3. 列出文档声明的可能原因。
4. 将每个原因对应到安全、可观察的检查操作。
5. 为操作定义可判定的验证结果。
6. 标注版本限制和危险操作审批要求。

## 可调用 MCP

只调用 `troubleshooting_query`。实际采集或写操作交由后续 RuntimeTask 和专项 Skill。

## 禁止行为

禁止直接执行排障命令、故障注入或修复；禁止把已知原因直接宣布为本次根因；禁止跨版本套用步骤。

## 退出条件

获得版本匹配的排障步骤与验证标准，或明确没有适用知识。

## 失败处理

无匹配条目时记录知识缺口；来源矛盾时保留限制并请求进一步 Evidence，而不是选择最方便的结论。

## 示例

针对重复订单，检索到检查相同业务标识请求次数、首个请求提交结果、响应延迟和幂等配置，并要求以证据验证而非直接认定根因。
