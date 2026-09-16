# 杨文魁 — Reasoning Engine 开发任务书

> 开发前先阅读根目录 `AGENTS.md` 与本文件。技术栈统一：Python 3.11+ / FastAPI / LangChain / Pydantic v2。

## 1. 模块定位

解决：**基于知识和现场证据，最可能是什么原因？下一步最值得验证什么？失败后如何调整思路？**

核心能力：Planner、Hypothesis、Evidence Planning、Root Cause Assessment、Reflection、CodeGraph Adapter、候选根因排序、证据引用与置信度。

核心循环：`Hypothesis → Evidence → Verification → Reflection`。

不负责：直接查 Trace/Log/Metric、直接执行 kubectl、故障注入、保存 Incident State、Runtime 状态跳转。

## 2. 代码边界

```text
src/ops_agent/reasoning/
skills/builtin/hypothesis-generation/
skills/builtin/evidence-planning/
skills/builtin/reflection/
src/ops_agent/integrations/mcp/code/
tests/reasoning/
docs/modules/04-reasoning.md
```

不得直接 import Knowledge/Investigation/Reproduction 的实现。

## 3. 必须实现的接口

至少：

```python
ReasoningPort.generate_hypotheses(...)
ReasoningPort.plan_evidence(...)
ReasoningPort.reflect(...)
ReasoningPort.verify_root_cause(...)
ReasoningPort.plan_experiment(...)
```

目标：`FakeReasoningEngine -> RealReasoningEngine`。

## 4. 输入/输出

输入：`ProblemContext`、标准 `KnowledgeContext`、`TroubleshootingContext`、`Evidence[]`、`ExperimentResult`、只读 Incident 上下文。不得直接读取 Product Skill Plugin manifest、入口文件或 Repository。

输出：`HypothesisSet`、`EvidencePlan`、`ReflectionResult`、`RootCauseAssessment`、`ExperimentPlan`。

必须严格引用真实 Evidence ID；禁止伪造证据、把推断写成事实、把“可能”写成“已确认”、用自由文本替代 Contract。

## 5. 第一阶段 MVP

统一 Case：首次请求已成功，但响应延迟触发重试，最终重复创建。

至少产生：

```text
H1 首次请求已成功，响应延迟触发客户端重试
H2 用户重复点击
H3 后端消息重复消费
```

要求：

1. 根据 Knowledge + Evidence 生成 3~5 个候选。
2. 每个候选包含 confidence、reason、supporting_evidence、contradicting_evidence、missing_evidence。
3. Evidence Plan 只说“要查什么”，不直接查询。
4. 实验失败时 Reflection 明确：失败原因、需补证据、是否调参数、是否换假设。
5. 能输出最终 RootCauseAssessment。

## 6. 小模型兼容

LangChain 仅在 Adapter 层；LLM 输出必须 Structured Output → Validator → Retry → Fallback；每次只处理当前 RuntimeTask，不允许让模型一次完成整个 Incident。

至少保留：`FakeLLMProvider`、`OpenAICompatibleProvider`。

## 7. 对接关系

| 对接模块 | 你消费 | 你输出 | 对接要求 |
|---|---|---|---|
| Knowledge | KnowledgeContext | Hypothesis | 不读取 Product Plugin/Obsidian 内部实现 |
| Investigation | Evidence[] | EvidencePlan | 只说明查什么，不直接查 |
| Reproduction | ExperimentResult | ExperimentPlan/Reflection | 不直接执行实验 |
| Runtime | RuntimeTask/Context | TaskResult | 不自己跳状态 |
| Integration | LLM Provider | Structured Reasoning | 确保小模型可调用 |

## 8. 测试要求

至少覆盖：Hypothesis 数量、confidence 范围、Evidence ID 合法性、Fact/Inference 分离、EvidencePlan 类型、Reflection 循环上限、非法 JSON、字段缺失、Retry/Fallback、小模型 Contract 一致性。

建议：

```text
tests/reasoning/test_hypothesis_generation.py
tests/reasoning/test_evidence_planning.py
tests/reasoning/test_root_cause_assessment.py
tests/reasoning/test_reflection.py
tests/reasoning/test_evidence_reference_validation.py
tests/reasoning/test_retry_fallback.py
```

## 9. 独立验收

组合：`FakeKnowledge + RealReasoning + FakeInvestigation + FakeReproduction`，完整 E2E 必须通过。

```bash
pytest tests/reasoning -q
pytest tests/contracts -q
pytest tests/e2e/test_fake_incident_flow.py -q
ruff check .
mypy src
```

最终验收：**RealReasoningEngine 替换 FakeReasoningEngine 后，无需修改其他模块，完整 E2E 仍通过。**

## 10. 交付物

RealReasoningEngine、Planner、Hypothesis Generator、Evidence Planner、Reflection、RootCauseAssessment、LLM Adapter、Validator/Retry/Fallback、测试、模块文档、Prompt/结构化输出说明、验证记录。
