# Module Ports v1

> 状态：Initial interface baseline  
> 日期：2026-09-15  
> Canonical package：`ops_agent.ports`

Ports 是 Runtime、Engine、Repository 和底层工具之间唯一允许的调用接口。所有 Port 使用 `@runtime_checkable Protocol`；全部方法为 `async`，输入输出只使用 `ops_agent.contracts` 中的 Pydantic v2 Model，不出现任意 `dict` 参数、LangChain 类型或 FastAPI Request/Response。

## 1. 调用模型

```text
Inbound API / Agent Host
          |
          v
      RuntimePort
          |
          v
   Engine Port interface
          |
          v
   Engine Service (后续实现)
          |
          v
      Tool Port
          |
          v
    Adapter / MCP
```

Reasoning 只生产 `EvidencePlan` 或 `ExperimentPlan`，不能调用 Investigation/Reproduction 实现：

```text
ReasoningPort.plan_evidence(...) -> EvidencePlan
Runtime 接纳并调度
InvestigationPort.collect_batch(EvidencePlan) -> EvidenceBatch
```

## 2. RuntimePort

产生者/实现者：Core Runtime。消费者：Inbound API、CLI、Agent Host。

```python
async def start_incident(command: StartIncidentRequest) -> IncidentState
async def get_next_task(query: IncidentQuery) -> RuntimeTask | None
async def submit_task_result(result: TaskResult) -> IncidentState
async def get_state(query: IncidentQuery) -> IncidentState
async def finish_incident(command: FinishIncidentRequest) -> RCAReport
```

| 方法 | 输入 Contract | 输出 Contract | 语义 |
|---|---|---|---|
| `start_incident` | `StartIncidentRequest` | `IncidentState` | 创建 Incident 并返回初始权威状态。 |
| `get_next_task` | `IncidentQuery` | `RuntimeTask \| None` | 由 Runtime 决定下一任务；无任务时返回 None。 |
| `submit_task_result` | `TaskResult` | `IncidentState` | 校验并接纳任务终态结果。 |
| `get_state` | `IncidentQuery` | `IncidentState` | 查询当前权威状态。 |
| `finish_incident` | `FinishIncidentRequest` | `RCAReport` | 在根因材料已验证后结束 Incident。 |

## 3. Engine Ports

### 3.1 KnowledgePort

实现者：Knowledge Service。消费者：Runtime。

```python
async def resolve_product(problem: ProblemContext) -> ProductContext
async def query_product_knowledge(query: KnowledgeQuery) -> KnowledgeContext
async def query_troubleshooting(query: KnowledgeQuery) -> TroubleshootingContext
```

Knowledge 生产 `ProductContext`、`KnowledgeContext`、`TroubleshootingContext`；Runtime 接纳后向 Reasoning 或其他步骤传递所需快照。

### 3.2 ReasoningPort

实现者：Reasoning Service。消费者：Runtime。

```python
async def generate_hypotheses(request: HypothesisGenerationRequest) -> HypothesisSet
async def plan_evidence(request: EvidencePlanningRequest) -> EvidencePlan
async def reflect(request: ReflectionRequest) -> ReflectionResult
async def verify_root_cause(request: RootCauseVerificationRequest) -> RootCauseAssessment
async def plan_experiment(request: ExperimentPlanningRequest) -> ExperimentPlan
```

Reasoning 生产候选、计划与评估，不执行采集、实验或状态转换。`ReflectionResult.next_action` 只是建议，最终决定由 Runtime 作出。

### 3.3 InvestigationPort

实现者：Investigation Service。消费者：Runtime。

```python
async def collect(request: EvidenceRequest) -> Evidence
async def collect_batch(plan: EvidencePlan) -> EvidenceBatch
```

Investigation 消费 Runtime 已批准的 Evidence Request/Plan，生产带来源和假设关联的 Evidence。它不能直接写 IncidentState。

### 3.4 ReproductionPort

实现者：Reproduction Service。消费者：Runtime。

```python
async def prepare(plan: ExperimentPlan) -> PreparedEnvironment
async def execute(request: ExperimentExecutionRequest) -> ExperimentResult
async def verify(request: ExperimentVerificationRequest) -> VerificationResult
async def cleanup(request: EnvironmentCleanupRequest) -> CleanupResult
```

Reproduction 生命周期显式分为准备、执行、验证、清理，方便 Runtime 在每一步应用 Policy、审批、deadline 与恢复策略。

## 4. StateRepositoryPort

实现者：内存或持久化 Adapter。消费者：Runtime。

```python
async def create(state: IncidentState) -> IncidentState
async def get(query: IncidentQuery) -> IncidentState | None
async def save(state: IncidentState) -> IncidentState
async def list_events(query: IncidentQuery) -> tuple[AuditEvent, ...]
async def append_event(event: AuditEvent) -> AuditEvent
```

Repository 只保存/读取完整 Contract；不暴露 ORM、数据库 session、查询构造器或供应商对象。`revision` 的并发语义将在 Runtime/Repository 实现步骤定义。

`append_event` 是 Step 4 为 Runtime 审计链增加的兼容接口扩展。Snapshot save 与 event append 的事务性由后续持久化 Adapter 定义。

## 4.1 ClockPort

实现者：生产时钟或确定性 Fake Clock。消费者：Runtime。

```python
async def now() -> datetime
```

ClockPort 隔离 wall clock，使 deadline、retry 和 AuditEvent 时间在测试中可完全确定。它返回标准库 timezone-aware datetime，不返回框架类型。

## 5. Investigation Tool Ports

实现者：Trace/Log/Metric/K8s/Change/Topology/CodeGraph Adapter 或 MCP Client。消费者：Investigation Service。

下列接口统一为：

```python
async def collect(request: EvidenceRequest) -> Evidence
```

- `TraceToolPort`
- `LogToolPort`
- `MetricToolPort`
- `K8sToolPort`
- `ChangeToolPort`
- `TopologyToolPort`
- `CodeGraphToolPort`

统一签名使 Fake 能确定性替代真实工具，同时由 `EvidenceRequest.evidence_type`、`acquisition_method` 和强类型时间窗表达采集意图。

## 6. Reproduction Tool Ports

实现者：Browser/API/Shell/Fault Injection Adapter 或 MCP Client。消费者：Reproduction Service。

```python
# BrowserToolPort / ApiToolPort / ShellToolPort
async def execute(request: ExperimentExecutionRequest) -> ExperimentResult

# FaultInjectionToolPort
async def apply(request: ExperimentExecutionRequest) -> ExperimentResult
async def rollback(request: EnvironmentCleanupRequest) -> CleanupResult
```

工具接收已经由 Runtime 接纳的计划和环境引用。Port 本身不绕过后续 Policy；真实实现仍必须遵守审批、作用域、超时和清理要求。

## 7. Port 操作 Contracts

Step 3 新增下列强类型调用对象，避免签名接收任意字典：

| Contract | 生产者 | 消费者 | 作用 |
|---|---|---|---|
| `IncidentQuery` | API/Runtime | Runtime/Repository | 关联 Incident 查询。 |
| `StartIncidentRequest` | Inbound Adapter | Runtime | 初始问题及可选上下文。 |
| `FinishIncidentRequest` | Runtime/受控调用方 | Runtime | 已验证评估和报告输入。 |
| `KnowledgeQuery` | Runtime | Knowledge | 版本感知知识请求。 |
| `HypothesisGenerationRequest` | Runtime | Reasoning | 生成假设所需完整快照。 |
| `EvidencePlanningRequest` | Runtime | Reasoning | 从假设生成采集计划。 |
| `ReflectionRequest` | Runtime | Reasoning | 有界反思快照。 |
| `RootCauseVerificationRequest` | Runtime | Reasoning | 根因评估输入。 |
| `ExperimentPlanningRequest` | Runtime | Reasoning | 复现实验规划输入。 |
| `EvidenceBatch` | Investigation | Runtime | 批量 Evidence 输出。 |
| `PreparedEnvironment` | Reproduction | Runtime | 已准备环境引用。 |
| `ExperimentExecutionRequest` | Runtime | Reproduction/Tool | 批准计划与环境。 |
| `ExperimentVerificationRequest` | Runtime | Reproduction | 实验验证输入。 |
| `EnvironmentCleanupRequest` | Runtime | Reproduction/Fault Tool | 显式环境清理命令。 |
| `CleanupResult` | Reproduction/Tool | Runtime | 清理结果。 |

这些新增类型遵循 Core Contracts v1 的通用信封、Pydantic v2、`extra="forbid"`、ID 和时间规则。它们扩展 v1 公共语言，但不改变 Step 2 已冻结模型。

## 8. Fake 兼容规则

- Protocol 不要求继承，Fake 只需以相同 async 签名结构实现。
- Fake 输入输出必须仍是 Contract，不能为了测试返回字典。
- 时间、ID 和输出应可固定，以支持确定性单元测试与 Fake E2E。
- 每个真实 Adapter 与 Fake 应复用相同的 Port contract test kit；该共享套件在后续实现步骤扩展。

## 9. 明确排除

本步骤没有定义 Engine Service 算法、Runtime 状态推进、Repository 持久化、MCP 调用、LangChain Agent、FastAPI 路由或真实工具行为。
