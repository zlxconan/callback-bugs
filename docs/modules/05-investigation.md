# Investigation Engine 模块模板

> 状态：Step 6 template complete  
> 默认运行方式：模块化单体、进程内 Port 调用

## 职责

Investigation Engine 接收单个 EvidenceRequest 或 EvidencePlan，协调未来的 Trace、Log、Metric、K8s、Change、Topology 与 CodeGraph Tool Port，并将采集结果标准化为 Evidence Contract。

Observability MCP 是环境插件化的工具执行能力。Reasoning 只规划 EvidenceRequest；Investigation 才能通过 Tool Port/MCP 采集并完成来源、时间、状态和假设关系标准化。

## 非职责

本模块不生成假设、不判断最终根因、不执行复现实验、不拥有 Evidence Graph 权威状态，也不直接推进 Runtime Stage。它不得直接调用 Reasoning 或 Reproduction 实现。

## 输入与输出

| 操作 | 输入 | 输出 |
|---|---|---|
| `collect` | `EvidenceRequest` | `Evidence` |
| `collect_batch` | `EvidencePlan` | `EvidenceBatch` |
| `health` | 无 | `ModuleHealth` |

## Ports 与调用方式

公共上层边界是 `InvestigationPort`；底层执行边界由本模块 `ports/` 重导出的各 Tool Port 定义。`InvestigationService` 实现上层 Protocol：

```text
Core Runtime -> InvestigationService -> InvestigationPort adapter -> Tool Ports
debug client -> FastAPI Router -> InvestigationService
```

MVP 走进程内调用，HTTP 只用于人工调试。未来拆分部署不改变 Service 与 Contract。

## Adapters、配置与错误

- `adapters/fake.py`：固定返回四项订单证据，并支持确定性失败/空批次。
- `adapters/`：未来 MCP、Observability SDK 和 Tool Port 组合实现。
- `domain/config.py`：冻结的 `InvestigationConfig`。
- `domain/errors.py`：模块错误、禁用错误和可重试依赖错误。
- `api/errors.py`：HTTP `ErrorResponse` 映射。
- `api/router.py`：单项、批量采集及模块健康调试端点。

## 测试

- `tests/investigation/test_module.py`：Port、Fake、Service、健康和禁用行为。
- `tests/investigation/test_contract.py`：EvidenceBatch HTTP 往返、健康与错误 Contract。
- Step 5 E2E 继续覆盖证据不足 Reflection 与采集失败重试超限。

## MVP

MVP 不读取真实 Trace/Logs/Metrics/K8s；`FakeInvestigationEngine` 只产生固定、带原始引用的 Evidence。

## Done 标准

Investigation 变更完成必须满足：采集输入输出 Contract-only；外部 SDK 仅在 Adapter；Service 可由 Runtime 进程内调用；Router 可独立调试；Fake、错误、健康和测试闭环完整；ruff、mypy、pytest 通过。

## 后续负责人开发目录

- 采集领域规则：`src/ops_agent/investigation/domain/`
- 用例入口：`src/ops_agent/investigation/service/`
- Engine/Tool Ports：`src/ops_agent/investigation/ports/`
- MCP/平台/Fake Adapter：`src/ops_agent/investigation/adapters/`
- HTTP 调试层：`src/ops_agent/investigation/api/`
- 测试：`tests/investigation/`
