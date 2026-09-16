# Reasoning Engine 模块模板

> 状态：Step 6 template complete  
> 默认运行方式：模块化单体、进程内 Port 调用

## 职责

Reasoning Engine 负责生成与排序假设、规划证据、受限反思、根因评估和实验规划。它只对给定 Contract 快照推理，并返回 Runtime 可校验的结构化决策。

## 非职责

本模块不采集证据、不执行工具或实验、不直接修改 IncidentState、不决定状态跳转，也不调用其他 Engine 实现。它不能绕过 Runtime 发起 Investigation 或 Reproduction。

Reasoning 只能消费 Knowledge Engine 已标准化的 KnowledgeContext/TroubleshootingContext，不得读取 Product Skill Plugin manifest、入口文件或 Repository。

## 输入与输出

| 操作 | 输入 | 输出 |
|---|---|---|
| `generate_hypotheses` | `HypothesisGenerationRequest` | `HypothesisSet` |
| `plan_evidence` | `EvidencePlanningRequest` | `EvidencePlan` |
| `reflect` | `ReflectionRequest` | `ReflectionResult` |
| `verify_root_cause` | `RootCauseVerificationRequest` | `RootCauseAssessment` |
| `plan_experiment` | `ExperimentPlanningRequest` | `ExperimentPlan` |
| `health` | 无 | `ModuleHealth` |

## Ports 与调用方式

公共边界是 `ReasoningPort`。`ReasoningService` 实现该 Protocol，并委托给注入的 Adapter。Runtime 仍是唯一编排者：

```text
Core Runtime -> ReasoningService -> ReasoningPort adapter
debug client -> FastAPI Router -> ReasoningService
```

Router 只是可选入站 Adapter，不是模块化单体内部默认传输。

## Adapters、配置与错误

- `adapters/fake.py`：固定 H1/H2/H3、证据计划、反思、评估和实验计划。
- `adapters/`：未来 LangChain/模型 Adapter 的唯一合法位置；输出必须转换成公共 Pydantic Contract。
- `domain/config.py`：冻结的 `ReasoningConfig`。
- `domain/errors.py`：模块错误、禁用错误和可重试依赖错误。
- `api/errors.py`：模块错误到 `ErrorResponse` 的 HTTP 映射。
- `api/router.py`：`/reasoning/*` 调试端点与模块健康端点。

## 测试

- `tests/reasoning/test_module.py`：Service 结构化实现、Fake 委托、健康和禁用行为。
- `tests/reasoning/test_contract.py`：Hypothesis Contract HTTP 往返、健康及错误 Contract。
- 架构测试必须确保 LangChain 不能进入 domain、contracts、ports 或 core。

## MVP

MVP 使用确定性 `FakeReasoningEngine`，不调用模型，不保存 Prompt，不实现真实推理策略。

## Done 标准

Reasoning 变更完成必须满足：所有五个 Port 方法保持 async 和 Contract-only；模型 SDK 不泄漏；Fake 可独立运行；Router 可调试；错误和健康结构化；模块测试、Contract 测试、ruff、mypy 与全量 pytest 通过。

## 后续负责人开发目录

- 推理领域约束：`src/ops_agent/reasoning/domain/`
- 用例入口：`src/ops_agent/reasoning/service/`
- Port 重导出：`src/ops_agent/reasoning/ports/`
- LLM/LangChain/Fake Adapter：`src/ops_agent/reasoning/adapters/`
- HTTP 调试层：`src/ops_agent/reasoning/api/`
- 测试：`tests/reasoning/`
