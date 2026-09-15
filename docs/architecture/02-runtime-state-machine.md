# Runtime State Machine v1

> 唯一定义：`ops_agent.core.runtime.controller.STATE_TRANSITIONS`

## 1. 状态图

```text
CREATED -> NORMALIZE -> KNOWLEDGE_LOOKUP -> HYPOTHESIS -> EVIDENCE_PLAN
                                                         |
                                                         v
                                                     INVESTIGATE
                                                       /     \
                                        evidence empty       evidence present
                                             /                   \
                                        REFLECT          ROOT_CAUSE_ASSESSMENT
                                          ^                   /          \
                                          |             unknown        assessed
                                          |                             |
                                          |                      EXPERIMENT_PLAN
                                          |                         /       \
                                          |                  approval       no approval
                                          |                    |                |
                                          |             WAITING_HUMAN ---------+
                                          |                    |
                                          +---- failed --- REPRODUCE
                                          |                    |
                                          +-- not confirmed -- VERIFY
                                                               |
                                                            confirmed
                                                               |
                                                              RCA
                                                               |
                                                            PERSIST
                                                               |
                                                           COMPLETED

Any active state -- terminal/non-retryable error or retry exhausted --> FAILED
```

## 2. 显式 Transition Table

| From | Allowed To |
|---|---|
| `CREATED` | `NORMALIZE`, `FAILED` |
| `NORMALIZE` | `KNOWLEDGE_LOOKUP`, `FAILED` |
| `KNOWLEDGE_LOOKUP` | `HYPOTHESIS`, `FAILED` |
| `HYPOTHESIS` | `EVIDENCE_PLAN`, `FAILED` |
| `EVIDENCE_PLAN` | `INVESTIGATE`, `FAILED` |
| `INVESTIGATE` | `ROOT_CAUSE_ASSESSMENT`, `REFLECT`, `FAILED` |
| `ROOT_CAUSE_ASSESSMENT` | `EXPERIMENT_PLAN`, `REFLECT`, `RCA`, `WAITING_HUMAN`, `FAILED` |
| `EXPERIMENT_PLAN` | `REPRODUCE`, `WAITING_HUMAN`, `FAILED` |
| `REPRODUCE` | `VERIFY`, `REFLECT`, `FAILED` |
| `VERIFY` | `RCA`, `REFLECT`, `FAILED` |
| `REFLECT` | `HYPOTHESIS`, `EVIDENCE_PLAN`, `ROOT_CAUSE_ASSESSMENT`, `EXPERIMENT_PLAN`, `RCA`, `WAITING_HUMAN`, `FAILED` |
| `RCA` | `PERSIST`, `FAILED` |
| `PERSIST` | `COMPLETED`, `FAILED` |
| `WAITING_HUMAN` | `HYPOTHESIS`, `EVIDENCE_PLAN`, `ROOT_CAUSE_ASSESSMENT`, `EXPERIMENT_PLAN`, `REPRODUCE`, `RCA`, `FAILED` |
| `COMPLETED` | 无 |
| `FAILED` | 无 |

所有状态变更必须调用 `transition_stage(current, target)`。不在表中的跳转抛出 `InvalidStateTransition`，业务 handler 无权绕过该表。

## 3. RuntimeStage 与 IncidentLifecycleStatus 映射

| RuntimeStage | IncidentLifecycleStatus |
|---|---|
| `CREATED` | `received` |
| `NORMALIZE`, `KNOWLEDGE_LOOKUP` | `contextualizing` |
| `HYPOTHESIS`, `EVIDENCE_PLAN` | `planning` |
| `INVESTIGATE` | `investigating` |
| `ROOT_CAUSE_ASSESSMENT`, `VERIFY`, `RCA`, `PERSIST` | `verifying` |
| `EXPERIMENT_PLAN` | `reproduction_planning` |
| `REPRODUCE` | `reproducing` |
| `REFLECT` | `reflecting` |
| `WAITING_HUMAN` | `waiting_approval` |
| `COMPLETED` | `resolved` |
| `FAILED` | `failed` |

粗粒度状态用于既有 Contract/API 兼容，细粒度 Stage 用于 Runtime 的确定性控制。

## 4. 停止条件

- RCA 已保存并完成 `PERSIST`：`COMPLETED`。
- 不可重试错误：`FAILED`。
- Retry 达到 `max_attempts`：`FAILED`。
- Reflection 达到 `max_reflection_loops`：暂停于 `WAITING_HUMAN`，不自动无限循环。
- 人工拒绝：`FAILED`。
- `COMPLETED`/`FAILED` 不产生后续任务；任何迟到 TaskResult 都被拒绝。

## 5. Result Handler Table

状态推进不是散落的流程 if/else。`CoreRuntime._result_handlers` 将每个可执行 Stage 映射到唯一 handler；handler 只能读取对应 `TaskOutput`、更新 IncidentState 的该阶段产物，并返回 Transition Table 中的候选目标。

分支只发生在明确定义的结果语义上：证据是否为空、根因是否 unknown、是否需要审批、实验是否成功、验证是否 confirmed、Reflection 的结构化 next action。所有分支最后仍通过统一 transition validator。

