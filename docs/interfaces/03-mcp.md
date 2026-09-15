# MCP Adapter v1

> 状态：Implemented  
> 日期：2026-09-15  
> 范围：Contract-first、传输无关的 MCP Adapter 与 Fake Tool

## 1. 定位

MCP 是外部 Agent 和内部 Engine 访问能力的执行边界，不是业务流程控制器。v1 提供 `McpToolRegistry`：每个 Tool 绑定现有 Pydantic 输入/输出 Contract、一个 Port 方法、权限风险和读写属性。JSON payload 在 Registry 入口立即执行 `model_validate`，Handler 只接收强类型对象；返回值再次按声明的 Contract 校验后才序列化。

```text
External Agent -> MCP transport binding (future) -> McpToolRegistry -> Port -> implementation
External Agent -> RuntimeMcpClient -> runtime-mcp -> Core Runtime -> RuntimeTask
Internal Engine -> Tool Port -> typed MCP client -> MCP registry/transport -> remote tool
```

MCP Server 不实现 Planner、Hypothesis、Reflection 或状态转换。Runtime 仍是 Incident State Machine 的唯一所有者。当前没有引入 MCP SDK 或网络 Server；未来 SDK 绑定只能读取 Registry 的 name、description、input/output JSON Schema 并调用 `registry.call`，不能复制业务模型。

## 2. Schema 与调用约定

- 表中的 Schema 名称均指 `ops_agent.contracts` 中已有的 Pydantic v2 Model，不是 MCP 私有 DTO。
- `McpTool.input_schema` 和 `output_schema` 直接调用 Contract 的 `model_json_schema()`。
- `incident_next` 是唯一 nullable 输出：`RuntimeTask | null`。
- MCP wire 层允许 JSON object；通过验证后不得继续传递任意 dict 作为业务输入。
- 所有成功输出使用 `model_dump(mode="json")`；调用方应以表中输出 Contract 重新验证。

## 3. Tool 清单

### 3.1 runtime-mcp

| Tool | 用途 | 输入 Schema | 输出 Schema | 对应 Port | 风险 | 写操作 |
|---|---|---|---|---|---|---|
| `incident_start` | 创建 Incident | `StartIncidentRequest` | `IncidentState` | `RuntimePort.start_incident` | medium | 是 |
| `incident_next` | 领取下一任务 | `IncidentQuery` | `RuntimeTask \| null` | `RuntimePort.get_next_task` | low | 否 |
| `incident_submit` | 提交任务结果并推进状态 | `TaskResult` | `IncidentState` | `RuntimePort.submit_task_result` | medium | 是 |
| `incident_get_state` | 读取权威状态 | `IncidentQuery` | `IncidentState` | `RuntimePort.get_state` | low | 否 |
| `incident_finish` | 完成 Incident 并生成报告 | `FinishIncidentRequest` | `RCAReport` | `RuntimePort.finish_incident` | medium | 是 |

这里的“写操作”表示改变 Runtime 权威状态。MCP 不自行决定下一 Stage，只转发已验证 Command/Result。

### 3.2 knowledge-mcp

| Tool | 用途 | 输入 Schema | 输出 Schema | 对应 Port | 风险 | 写操作 |
|---|---|---|---|---|---|---|
| `product_query` | 从问题解析产品上下文 | `ProblemContext` | `ProductContext` | `KnowledgePort.resolve_product` | low | 否 |
| `version_query` | 查询版本适用的产品知识 | `KnowledgeQuery` | `KnowledgeContext` | `KnowledgePort.query_product_knowledge` | low | 否 |
| `troubleshooting_query` | 查询结构化排障知识 | `KnowledgeQuery` | `TroubleshootingContext` | `KnowledgePort.query_troubleshooting` | low | 否 |

### 3.3 observability-mcp

| Tool | 用途 | 输入 Schema | 输出 Schema | 对应 Port | 风险 | 写操作 |
|---|---|---|---|---|---|---|
| `trace_query` | 查询调用链 | `EvidenceRequest` | `Evidence` | `TraceToolPort.collect` | low | 否 |
| `log_query` | 查询日志 | `EvidenceRequest` | `Evidence` | `LogToolPort.collect` | low | 否 |
| `metric_query` | 查询指标 | `EvidenceRequest` | `Evidence` | `MetricToolPort.collect` | low | 否 |
| `k8s_inspect` | 检查 Kubernetes 资源 | `EvidenceRequest` | `Evidence` | `K8sToolPort.collect` | low | 否 |
| `change_query` | 查询变更历史 | `EvidenceRequest` | `Evidence` | `ChangeToolPort.collect` | low | 否 |
| `topology_query` | 查询服务拓扑 | `EvidenceRequest` | `Evidence` | `TopologyToolPort.collect` | low | 否 |

当前均建模为只读采集。未来若增加 K8s 写操作，必须使用新 Tool 名、显式写标记和更高风险等级，不能扩展 `k8s_inspect` 的语义。

### 3.4 code-mcp

| Tool | 用途 | 输入 Schema | 输出 Schema | 对应 Port | 风险 | 写操作 |
|---|---|---|---|---|---|---|
| `code_search` | 搜索代码并返回引用 | `EvidenceRequest` | `Evidence` | `CodeGraphToolPort.collect` | low | 否 |
| `call_graph` | 查询调用关系 | `EvidenceRequest` | `Evidence` | `CodeGraphToolPort.collect` | low | 否 |
| `stack_trace_analysis` | 将堆栈关联到代码 | `EvidenceRequest` | `Evidence` | `CodeGraphToolPort.collect` | low | 否 |

三种视图共享 Port，但保留不同 Tool 名以便权限、审计和未来 Adapter 路由独立演进。

### 3.5 reproduction-mcp

| Tool | 用途 | 输入 Schema | 输出 Schema | 对应 Port | 风险 | 写操作 |
|---|---|---|---|---|---|---|
| `browser_action` | 执行受控浏览器动作 | `ExperimentExecutionRequest` | `ExperimentResult` | `BrowserToolPort.execute` | medium | 是 |
| `api_call` | 执行受控 API 调用 | `ExperimentExecutionRequest` | `ExperimentResult` | `ApiToolPort.execute` | medium | 是 |
| `shell_execute` | 执行受控 Shell 操作 | `ExperimentExecutionRequest` | `ExperimentResult` | `ShellToolPort.execute` | high | 是 |
| `fault_inject` | 执行已批准的故障注入 | `ExperimentExecutionRequest` | `ExperimentResult` | `FaultInjectionToolPort.apply` | high | 是 |
| `experiment_execute` | 执行完整实验 | `ExperimentExecutionRequest` | `ExperimentResult` | `ReproductionPort.execute` | high | 是 |
| `experiment_cleanup` | 清理实验环境 | `EnvironmentCleanupRequest` | `CleanupResult` | `ReproductionPort.cleanup` | medium | 是 |

`write=true` 只是能力声明，不是授权。真实实现仍必须经过 Runtime Policy、Human Approval、环境隔离、超时和审计；Registry v1 不代替这些控制。

## 4. 错误码

所有 MCP 边界错误携带现有 `ErrorResponse` Contract，由 `McpInvocationError.error` 暴露。

| 错误码 | 类别 | retryable | 含义 |
|---|---|---|---|
| `MCP_TOOL_NOT_FOUND` | `terminal` | 否 | Tool 未注册或名称错误 |
| `MCP_INPUT_VALIDATION_ERROR` | `validation` | 否 | 输入未通过声明 Contract 的 Pydantic 校验 |
| `MCP_TOOL_EXECUTION_ERROR` | `dependency` | 是 | Port/Adapter 执行异常或输出 Contract 校验失败 |

Runtime/Engine 返回的细粒度业务错误未来可由传输绑定保留；不得转成自由文本后丢失 `incident_id/request_id/source/timestamp`。

## 5. Fake 实现

- `FakeEvidenceTool` 实现所有 `collect(EvidenceRequest) -> Evidence` 形状的低层 Tool Port，不访问观测或代码系统。
- `FakeExecutionTool` 实现 browser/API/Shell 的 `execute` 以及 fault 的 `apply/rollback`，不产生外部副作用。
- Knowledge 与完整实验继续复用 Step 5 的 `FakeKnowledgeEngine`、`FakeReproductionEngine`。
- `RuntimeMcpClient` 结构化实现 `RuntimePort`，用于证明 External Agent 可以只通过 runtime-mcp 管理 Incident。
- `EvidenceMcpClient`、`ExecutionMcpClient` 与 `FaultInjectionMcpClient` 分别结构化实现采集、执行和故障注入 Tool Port，可直接注入内部 Engine。
- `KnowledgeMcpClient` 结构化实现 `KnowledgePort`，为未来 Knowledge 独立部署保留相同业务边界。

## 6. Fake E2E

测试链路为：

```text
FakeIncidentRunner (External Agent substitute)
  -> RuntimeMcpClient
  -> runtime-mcp Registry
  -> CoreRuntime
  -> RuntimeTask
  -> Fake Engine Ports
  -> TaskResult
  -> runtime-mcp
  -> CoreRuntime
  -> COMPLETED + RCAReport
```

这符合 External Agent Reasoning Owner 原则：Core Runtime 通过 RuntimeTask 指定工作，不直接 import Fake Engine；Agent 根据任务调用 Fake Engine Port，再通过 `incident_submit` 交回结果。

## 7. 测试与 Done 标准

- `tests/integration/mcp/test_contracts.py`：Tool 完整性、Schema 身份、风险与读写属性。
- `tests/integration/mcp/test_fake_tools.py`：输入/输出 Contract、Fake Knowledge/Observability/Code/Reproduction 以及标准错误。
- `tests/integration/mcp/test_runtime_e2e.py`：External Agent 经 Runtime MCP 完成 Step 5 全链路。

Step 7 Done 要求：23 个 Tool 全部注册；输入输出复用公共 Contract；Fake 无外部连接；Runtime E2E 到 `COMPLETED`；MCP 不包含 Planner/Hypothesis/Reflection/状态机；pytest、ruff、格式与 mypy 全部通过。

## 8. v1 限制与后续边界

- 当前是 MCP Adapter 核心，不是可监听 stdio/HTTP 的真实 MCP Server；未引入具体 MCP SDK。
- Registry 尚未实现认证、租户隔离、速率限制、审批令牌或分布式 tracing。
- 当前 typed client 调用进程内 Registry；真实 stdio/HTTP 传输只允许替换 client 的调用通道，不得改变 Port 和 Contract。
- 真实只读查询和写操作必须在后续步骤分别实现安全 Adapter，不能修改当前 Contract 语义。
