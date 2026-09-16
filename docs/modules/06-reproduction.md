# Reproduction Engine

> 状态：第三阶段 Real Engine + Playwright + Toxiproxy Adapters complete
> 默认运行方式：模块化单体、进程内 Port 调用

## 职责

Reproduction Engine 管理单次受控实验的环境准备、执行、结果验证和清理。未来通过 Browser、API、Shell 和 FaultInjection Tool Port 执行 Runtime 已批准的 ExperimentPlan。

`reproduction-planning` 是 Core Built-in Method Skill；Playwright、Toxiproxy、mitmproxy、k6、Chaos Mesh 是 Reproduction MCP/Adapter。具体工具步骤不得写死进 Core Runtime。

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
- `adapters/browser/playwright.py`：`BrowserToolPort` 的最小真实 Playwright 实现，仅封装
  MVP 需要的页面打开、填写、点击、等待、网络观测、页面状态提取与截图。
- `adapters/fault_injection/toxiproxy.py`：`FaultInjectionToolPort` 的 Toxiproxy HTTP API
  实现，为每个 Experiment Environment 建立独立 Proxy 和 downstream latency Toxic。
- `service/reproduction_engine.py`：实现既有 `ReproductionPort` 的 RealReproductionEngine。
- `service/experiment_runner.py`：依次调用 API prepare、Fault、Browser、API evidence Tool Port。
- `service/verifier.py`：四条确定性规则，不使用 LLM。
- `service/cleanup_manager.py`：按 environment ref 幂等 rollback，并记录 cleanup 失败。
- `integrations/mcp/fake.py`：可注入的 Fake Browser/API/Shell/Fault Tool Adapter。
- `adapters/`：未来 Playwright、API、Shell、k6、Toxiproxy、Chaos Mesh 或 MCP 真实实现。
- `domain/config.py`：模块开关、Tool timeout 和允许的隔离环境类型。
- `domain/environment_policy.py`：拒绝 production、外部系统和未允许环境。
- `domain/errors.py`：模块、禁用、策略、依赖和 timeout 错误。
- `api/errors.py`：HTTP `ErrorResponse` 映射。
- `api/router.py`：实验生命周期与模块健康调试端点。

第三阶段将 FaultInjection Tool 替换为真实 Toxiproxy Adapter。API 与 Shell 仍使用
确定性 Fake Adapter；mitmproxy、k6 和 Chaos Mesh 未接入。
Playwright 依赖只存在于 `reproduction/adapters/browser/`，`domain/` 和 `service/` 不导入它。
Toxiproxy HTTP API 只在 `reproduction/adapters/fault_injection/` 中调用，不进入 domain/service。
资源名由 Environment Ref 和稳定 hash 构成；cleanup 只移除当前实验的 Toxic/Proxy，
不调用 Toxiproxy 全局 `/reset`。
每次执行使用独立 Browser Context，成功或失败都关闭 Context 和 Browser；清理错误会记录，
不覆盖原始操作异常。

## 第一阶段固定规则

Verifier 从标准 `ExperimentResult.outputs` 判断：

1. 同一 business ID 的 request count 至少为 2；
2. 第一次请求 backend status 为 success；
3. 检测到客户端 retry；
4. 数据库 record count 恰好为 2。

四项全部匹配返回 `VerificationStatus.CONFIRMED`；任一不匹配返回 `REJECTED`。matched/unmatched criteria
分别进入 `confirmed_claims`/`rejected_claims`，结论同时记录在 rationale 和 metadata，Evidence ID 原样关联。

`prepare` 部分失败、fault/browser/API 执行失败、timeout 和 verify 异常均触发 cleanup。verify 正常结束也
cleanup，调用方随后显式 cleanup 是安全 no-op。Cleanup 失败保存于 CleanupManager，不会覆盖原始执行异常。

## 测试

- `tests/reproduction/test_module.py`：Port、Fake、Service、健康与禁用行为。
- `tests/reproduction/test_contract.py`：ExperimentResult HTTP 往返、健康与错误 Contract。
- `tests/reproduction/test_real_engine.py`：Real lifecycle、Verifier、安全、timeout、失败 cleanup 与幂等性。
- `tests/reproduction/test_playwright_browser_adapter.py`：Adapter Contract 映射，以及真实 Chromium 对本地
  HTTP 页面的集成、timeout、selector/page 错误、截图证据与清理。
- `tests/reproduction/test_toxiproxy_adapter.py`：Proxy/Toxic 创建与幂等移除、API 不可用、
  timeout、失败 cleanup、实验隔离，以及真实 Toxiproxy + Chromium Runtime E2E。
- `tests/e2e/test_real_reproduction_incident_flow.py`：三个 Fake Engine + RealReproduction 的替换 E2E。
- `tests/e2e/test_playwright_reproduction_incident_flow.py`：三个 Fake Engine + RealReproduction +
  Playwright Browser + Fake Fault/API/Shell 的 Runtime E2E。
- Step 5 E2E 继续覆盖完整实验、H1 验证和执行失败重试超限。

## MVP

RealReproductionEngine 可使用真实 Chromium + Toxiproxy 运行本地
timeout/retry/duplicate-create Lab，并输出代理、延迟、请求、页面状态和截图证据。
测试环境需先安装 Python 依赖、Chromium，并可访问 Docker daemon：

```bash
uv sync --extra dev
.venv/bin/python -m playwright install chromium
```

真实集成测试启动临时 `ghcr.io/shopify/toxiproxy:2.12.0` 容器，让无内置延迟的
测试后端经过 80ms downstream latency Toxic。客户端 20ms 超时后重试，实验结束
移除 Toxic 和 Proxy。Docker 不可用时真实容器用例会显式 skip，其余 Contract/错误/
隔离测试仍执行。

## Done 标准

Reproduction 变更完成必须满足：四阶段生命周期全部使用 Contract；危险能力仍由 Runtime Policy/Approval 管理；Service 可进程内调用；Router 可调试；清理、错误、健康和 Fake 可测试；ruff、mypy、pytest 全部通过。

## 后续负责人开发目录

- 实验领域规则：`src/ops_agent/reproduction/domain/`
- 用例入口：`src/ops_agent/reproduction/service/`
- Engine/Tool Ports：`src/ops_agent/reproduction/ports/`
- 执行/Fake Adapter：`src/ops_agent/reproduction/adapters/`
- HTTP 调试层：`src/ops_agent/reproduction/api/`
- 测试：`tests/reproduction/`
