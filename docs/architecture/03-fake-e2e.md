# Fake Engine 与首个端到端闭环

> 状态：Implemented  
> 日期：2026-09-15  
> 范围：Step 5，仅确定性 Fake，不连接任何真实外部系统

## 1. 目标与边界

本步骤证明 Step 2 Contracts、Step 3 Ports 与 Step 4 Core Runtime 可以组成一个完整的模块化单体工作流。固定场景是：创建订单的首次请求已在后端成功，但响应延迟超过客户端超时；客户端自动重试，而非幂等创建接口再次创建订单。

所有输入、知识、证据、实验结果和时间均为内存中的固定数据。实现不访问网络、数据库、日志平台、Kubernetes、浏览器、Shell、LLM 或 MCP。

## 2. Fake 组件

| 组件 | 实现的 Port | 固定职责 |
|---|---|---|
| `FakeKnowledgeEngine` | `KnowledgePort` | 解析固定产品版本，返回“支持客户端重试”和“创建接口非幂等”两项知识 |
| `FakeReasoningEngine` | `ReasoningPort` | 生成 H1/H2/H3、规划四项证据、评估根因、规划实验并处理反思 |
| `FakeInvestigationEngine` | `InvestigationPort` | 返回两次同业务请求、首次成功、首次响应延迟、第二次成功四项证据 |
| `FakeReproductionEngine` | `ReproductionPort` | 准备内存环境，模拟超时重试产生两个订单，验证 H1 并清理环境 |
| `InMemoryStateRepository` | `StateRepositoryPort` | 深拷贝保存 IncidentState 与 AuditEvent，避免调用方绕过 Runtime 修改权威状态 |
| `FakeIncidentRunner` | Port consumer | 领取 RuntimeTask，按 Stage 调用 Engine Port，并提交强类型 TaskResult |

Fake Engine 使用结构化 Contract 作为唯一输入输出，不暴露 LangChain 或 FastAPI 类型。E2E 测试通过 `runtime_checkable Protocol` 和 mypy 的结构类型检查同时验证 Port 兼容性。

## 3. Runtime 编排链

正常路径由 Runtime 实际生成任务并接受结果：

```text
CREATED
  -> NORMALIZE
  -> KNOWLEDGE_LOOKUP
  -> HYPOTHESIS
  -> EVIDENCE_PLAN
  -> INVESTIGATE
  -> ROOT_CAUSE_ASSESSMENT
  -> EXPERIMENT_PLAN
  -> REPRODUCE
  -> VERIFY
  -> RCA
  -> PERSIST
  -> COMPLETED
```

测试只提交初始 `StartIncidentRequest`，不直接赋值或修改 `IncidentState`。`FakeIncidentRunner` 也只依赖 `RuntimePort` 与四个 Engine Port；它无法取得 Repository 写入口。Runtime 仍是唯一状态转换与生命周期所有者。

最终状态包含：

- H1：首次请求成功但响应延迟，客户端重试导致再次创建；
- H2：前端重复点击；
- H3：消息队列重复消费；
- E-1 至 E-4 的原始引用、结构化值及假设关系；
- EXP-1 的最小实验步骤与两个订单的结果；
- 对 H1 的 confirmed 验证；
- 分离的事实、推断、根因、最小复现条件、修复建议、未验证项和证据链。

完整、可反序列化的运行快照保存在 [duplicate-order-timeout-retry.json](../../examples/incidents/duplicate-order-timeout-retry.json)。测试会重新运行同一工作流并与该文件做 Pydantic 模型级等值比较，以防示例漂移。

## 4. 失败与回环

Fake 支持有限的故障注入参数，但不执行真实故障注入：

- `FakeInvestigationEngine(fail_times=n)` 使前 n 次采集抛出瞬时错误；Runner 将其转换为 retryable `ErrorResponse`，由 Runtime 决定重试或进入 `FAILED`。
- `FakeReproductionEngine(fail_times=n)` 对实验执行应用同一错误路由，验证 Reproduction 重试超限行为。
- `FakeInvestigationEngine(empty_batch_times=1)` 首次返回空 EvidenceBatch；Runtime 进入 `REFLECT`，Reasoning 返回 `COLLECT_EVIDENCE`，Runtime 再次进入 `EVIDENCE_PLAN -> INVESTIGATE`，随后完成全流程。

这些分支均不在测试或 Runner 中手工跳转 Stage。

## 5. Contract 兼容扩展

RCA 必须表达最小复现条件，因此 `RCAReport` 与 `FinishIncidentRequest` 增加了带默认空列表的 `minimal_reproduction_conditions`。这是 v1 的向后兼容扩展：已有 JSON 仍可验证，Runtime 的 `finish_incident` 会原样传递该字段。字段一旦被外部消费者采用，其重命名、删除或语义变更仍需新 Contract 版本。

## 6. 验证范围

`tests/e2e/test_fake_incident_flow.py` 覆盖：

1. 完整固定场景到 `COMPLETED`；
2. 五个 Fake 对相应 Protocol 的运行时兼容性；
3. Investigation 连续失败并由 Runtime 重试超限进入 `FAILED`；
4. Reproduction 连续失败并由 Runtime 重试超限进入 `FAILED`；
5. 证据不足触发 Reflection 后重新规划、采集并完成；
6. 保存的 Incident 示例与实际 Runtime 输出完全一致。

验证命令：

```bash
.venv/bin/pytest tests/e2e/test_fake_incident_flow.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src tests
.venv/bin/pytest
```

## 7. 当前限制

- Fake 的内容仅用于架构闭环，不代表任何真实产品版本行为或生产根因。
- InMemoryStateRepository 不提供跨进程持久化、事务、并发控制或重启恢复。
- Runner 是本地 External Agent 模式的确定性替身，不是通用 Agent 实现。
- 本步骤未实现真实知识源、可观测平台、实验环境、LLM、MCP、API 工作流入口或生产安全策略。
