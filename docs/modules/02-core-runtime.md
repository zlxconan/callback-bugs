# Core Runtime v1

> 状态：Implemented  
> 日期：2026-09-15  
> 实现：`ops_agent.core.runtime.CoreRuntime`

## 1. 定位

Core Runtime 是唯一工作流编排者。v1 采用纯确定性控制器：给定持久化的 `IncidentState`、当前时钟、`RuntimeConfig` 和提交的 `TaskResult`，下一阶段完全由显式 Transition Table 与结果 handler table 决定。

Runtime 不依赖 LangChain、OpenAI、Qwen、GLM、Codex 或 CodeBuddy，也不包含 Prompt、模型选择或推理实现。External Agent 与未来 Local Agent 都以相同方式领取 `RuntimeTask`、返回 `TaskResult`，Runtime 无需改变。

## 2. 兼容 Contract 决策

Step 2 已冻结的 `IncidentState.status` 使用粗粒度 `IncidentLifecycleStatus`，不能唯一表达 HYPOTHESIS、EVIDENCE_PLAN 等阶段。因此 v1 做兼容扩展：

- 保留 `status` 及其原有语义。
- 新增可选 `runtime_stage: RuntimeStage` 表达细粒度阶段。
- 新增 `pending_task`、`resume_stage`、`reflection_count`、`last_error` 和阶段产物字段。
- `RuntimeTask` 新增可选 `stage`。
- `TaskResult` 新增可选 `typed_output: TaskOutput`，保留既有 `output` 以兼容原 JSON。

这些字段都有默认值，旧 v1 JSON 仍能反序列化；CoreRuntime 创建的新 Incident 总是设置 `runtime_stage`。Runtime 只接受强类型 `TaskOutput` 推进工作流。

## 3. 公共入口

`CoreRuntime` 实现 `RuntimePort`：

```python
async def start_incident(command: StartIncidentRequest) -> IncidentState
async def get_next_task(query: IncidentQuery) -> RuntimeTask | None
async def submit_task_result(result: TaskResult) -> IncidentState
async def get_state(query: IncidentQuery) -> IncidentState
async def finish_incident(command: FinishIncidentRequest) -> RCAReport
```

- `start_incident` 创建 `CREATED` 状态并记录 `incident.created`。
- `get_next_task` 根据当前 Stage 产生唯一待处理任务；同一任务未结束时重复调用返回同一任务。
- `submit_task_result` 校验 Incident、Request、Task ID、Stage、deadline 和强类型输出后推进状态。
- `get_state` 读取权威快照。
- `finish_incident` 是 RCA 阶段的确定性报告完成入口，不做根因推理。

## 4. Reasoning Owner

RuntimeTask 的 `kind + stage` 指定由谁完成工作：

| Stage | TaskKind | 预期 TaskOutput |
|---|---|---|
| `NORMALIZE` | `normalization` | `problem` |
| `KNOWLEDGE_LOOKUP` | `knowledge` | `knowledge_lookup` |
| `HYPOTHESIS` | `reasoning` | `hypotheses` |
| `EVIDENCE_PLAN` | `reasoning` | `evidence_plan` |
| `INVESTIGATE` | `investigation` | `evidence_batch` |
| `ROOT_CAUSE_ASSESSMENT` | `reasoning` | `root_cause_assessment` |
| `EXPERIMENT_PLAN` | `reasoning` | `experiment_plan` |
| `REPRODUCE` | `reproduction` | `experiment_result` |
| `VERIFY` | `verification` | `verification_result` |
| `REFLECT` | `reflection` | `reflection_result` |
| `RCA` | `reasoning` | `rca_report` |
| `WAITING_HUMAN` | `human_approval` | `human_decision` |

`TaskOutput` 要求恰好一个结果字段非空，避免 Runtime 解析自由字典。External Agent、Local Agent Adapter 或测试 Fake 均遵守同一表。

## 5. Retry 与 Timeout

`RuntimeConfig`：

- `max_attempts`：单阶段任务最大尝试次数，默认 3。
- `task_timeout_seconds`：每次任务 deadline，默认 30 秒。
- `max_reflection_loops`：无人介入前允许的 Reflection 次数，默认 2。

失败路由规则：

1. `TaskResult.status != succeeded` 进入统一 error router。
2. `ErrorResponse.retryable=true` 且未达到 `max_attempts`，在同一 Stage 创建新 Task，`attempt + 1`。
3. 超过 deadline 生成 `TASK_TIMEOUT`，按可重试错误处理。
4. 非重试错误或尝试耗尽转入 `FAILED`。
5. `FAILED` 和 `COMPLETED` 不再生成任务，且拒绝新的 TaskResult。

时钟由 `ClockPort` 注入，因此 timeout 测试无需真实等待。

## 6. Reflection 与人工介入

- Investigation 返回空 `EvidenceBatch` 时进入 `REFLECT`。
- 实验失败或 Verification 非 confirmed 时进入 `REFLECT`。
- Runtime 只读取 `ReflectionResult.next_action`，通过固定映射选择候选目标 Stage。
- 达到最大循环次数时进入 `WAITING_HUMAN`，并保存 `resume_stage`。
- `ExperimentPlan.requires_approval=true` 时进入 `WAITING_HUMAN`，批准后恢复到 `REPRODUCE`。
- 拒绝人工请求进入 `FAILED`。

HumanDecision 只包含批准结果、决策人和原因；Runtime 不自行推断人的意图。

## 7. Audit Event

Runtime 为以下事件写入 `StateRepositoryPort.append_event`：

- `incident.created`
- `stage.transition`
- `task.created`
- `task.accepted`
- `task.failed`
- `task.timed_out`
- `task.retry_scheduled`
- `incident.failed`
- `incident.completed`

Audit ID 和 previous event link 根据仓库已有事件确定，测试使用固定时钟和内存 Fake，可稳定复现。

## 8. 确定性与边界

Runtime 只 import：

- Python 标准库
- Pydantic v2（配置 value object）
- `ops_agent.contracts`
- `ops_agent.ports`

Runtime 不分析日志、不生成 Hypothesis、不调用 LLM、不执行实验或故障注入。Task 的真正执行由外部 Agent 或未来的 Engine/Local Agent Adapter 完成。

## 9. v1 限制

- Repository v1 的 snapshot save 与 audit append 是两个 Port 调用，尚未定义事务性 outbox；生产持久化实现必须处理部分失败。
- RuntimeTask 使用确定性、可读 ID；分布式多 Runtime 写入时仍需 Repository 的 revision/乐观锁实现。
- `PERSIST` 当前表示权威状态和 RCA 已保存，尚不包含外部知识库发布。
- Human approval 尚无身份认证或签名校验；这些属于 API/Policy/Adapter 后续步骤。

