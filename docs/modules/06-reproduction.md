# Reproduction Engine 模块模板

> 状态：Step 6 template complete  
> 默认运行方式：模块化单体、进程内 Port 调用

## 职责

Reproduction Engine 管理单次受控实验的环境准备、执行、结果验证和清理。未来通过 Browser、API、Shell 和 FaultInjection Tool Port 执行 Runtime 已批准的 ExperimentPlan。

## 非职责

本模块不自行选择根因、不规划跨 Engine 工作流、不绕过 Human Approval、不修改 IncidentState，也不决定是否结束 Incident。它不能直接调用 Knowledge、Reasoning 或 Investigation 实现。

## 输入与输出

| 操作 | 输入 | 输出 |
|---|---|---|
| `prepare` | `ExperimentPlan` | `PreparedEnvironment` |
| `execute` | `ExperimentExecutionRequest` | `ExperimentResult` |
| `verify` | `ExperimentVerificationRequest` | `VerificationResult` |
| `cleanup` | `EnvironmentCleanupRequest` | `CleanupResult` |
| `health` | 无 | `ModuleHealth` |

## Ports 与调用方式

公共上层边界是 `ReproductionPort`，底层执行边界由本模块重导出的 Browser、API、Shell 与 FaultInjection Tool Port 提供：

```text
Core Runtime -> ReproductionService -> ReproductionPort adapter -> Tool Ports
debug client -> FastAPI Router -> ReproductionService
```

当前 Runtime 使用 async Python Port，不通过 HTTP 调用 Engine。

## Adapters、配置与错误

- `adapters/fake.py`：内存模拟首次响应延迟、一次客户端重试和两个订单。
- `adapters/`：未来 Playwright、API、Shell、k6、Toxiproxy、Chaos Mesh 或 MCP 实现。
- `domain/config.py`：冻结的 `ReproductionConfig`。
- `domain/errors.py`：模块错误、禁用错误和可重试依赖错误。
- `api/errors.py`：HTTP `ErrorResponse` 映射。
- `api/router.py`：实验生命周期与模块健康调试端点。

## 测试

- `tests/reproduction/test_module.py`：Port、Fake、Service、健康与禁用行为。
- `tests/reproduction/test_contract.py`：ExperimentResult HTTP 往返、健康与错误 Contract。
- Step 5 E2E 继续覆盖完整实验、H1 验证和执行失败重试超限。

## MVP

MVP 的 `FakeReproductionEngine` 不启动浏览器、进程、代理或故障注入平台，不产生真实副作用。

## Done 标准

Reproduction 变更完成必须满足：四阶段生命周期全部使用 Contract；危险能力仍由 Runtime Policy/Approval 管理；Service 可进程内调用；Router 可调试；清理、错误、健康和 Fake 可测试；ruff、mypy、pytest 全部通过。

## 后续负责人开发目录

- 实验领域规则：`src/ops_agent/reproduction/domain/`
- 用例入口：`src/ops_agent/reproduction/service/`
- Engine/Tool Ports：`src/ops_agent/reproduction/ports/`
- 执行/Fake Adapter：`src/ops_agent/reproduction/adapters/`
- HTTP 调试层：`src/ops_agent/reproduction/api/`
- 测试：`tests/reproduction/`
