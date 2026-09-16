# MCP Interface Boundary v0.2

MCP 是工具执行接口，不是业务方法论、Skill Registry 或工作流控制器。Tool 输入输出继续映射既有 Pydantic Contract；MCP 层不得定义第二套业务对象。

## 1. Runtime MCP（Core）

| Tool | Contract | 对应 Port | 写操作 |
|---|---|---|---:|
| `incident_start` | StartIncidentRequest -> IncidentState | RuntimePort.start_incident | 是 |
| `incident_next` | IncidentQuery -> RuntimeTask/null | RuntimePort.get_next_task | 否 |
| `incident_submit` | TaskResult -> IncidentState | RuntimePort.submit_task_result | 是 |
| `incident_get_state` | IncidentQuery -> IncidentState | RuntimePort.get_state | 否 |
| `incident_finish` | FinishIncidentRequest -> RCAReport | RuntimePort.finish_incident | 是 |

Runtime MCP 只转发/校验，不决定下一 Stage。

## 2. Observability MCP（环境插件）

`trace_query`、`log_query`、`metric_query`、`k8s_inspect`、`change_query`、`topology_query` 均接收 EvidenceRequest、返回 Evidence，并映射对应 Tool Port。Investigation Engine 负责调用和 Evidence 标准化；Reasoning 不直接调用这些工具。

## 3. Code MCP

`code_search`、`call_graph`、`stack_trace_analysis` 返回可引用 Evidence。代码查询不能直接改变 Hypothesis 或 Runtime 状态。

## 4. Reproduction MCP（工具/环境插件）

| Tool | 风险 | 写操作 |
|---|---:|---:|
| `browser_action` | medium | 是 |
| `api_call` | medium | 是 |
| `shell_execute` | high | 是 |
| `fault_inject` | high | 是 |
| `experiment_execute` | high | 是 |
| `experiment_cleanup` | medium | 是 |

Playwright、Toxiproxy、mitmproxy、k6、Chaos Mesh 是这些 Port/MCP 的具体 Adapter。Tool 声明不等于授权，仍需 Runtime Policy、Human Approval、作用域、超时、审计和 cleanup。

## 5. Knowledge 边界

具体 Product Skill 不注册为 Core MCP。Product/Troubleshooting Skill 首先是外部 Plugin Package，由 Generic Skill Runtime 发现与解析，再由 Knowledge Engine 输出标准 KnowledgeContext。

当前 `knowledge-mcp` 的 `product_query`、`version_query`、`troubleshooting_query` 仅是 **KnowledgePort 的可选远程部署 Adapter**。它不能分发 Product Skill、实现 crawler 或成为 Runtime 读取插件文件的旁路。模块化单体默认仍使用进程内 KnowledgePort。

## 6. 禁止职责

任何 MCP Server 都不得实现 Planner、Hypothesis Generation、Evidence Planning、Reflection、RCA 方法论、Incident State Machine 或 Product Skill 内容管理。

## 7. 错误与验证

现有错误保持：`MCP_TOOL_NOT_FOUND`、`MCP_INPUT_VALIDATION_ERROR`、`MCP_TOOL_EXECUTION_ERROR`，均携带 ErrorResponse。Registry 继续负责输入/输出 Schema 验证，真实传输、认证、租户隔离和限流仍未实现。
