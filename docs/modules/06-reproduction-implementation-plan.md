# Reproduction Engine 第一阶段实施计划

> 状态：Current-state audit / implementation proposal
> 负责人：王亚东
> 审计日期：2026-09-16
> 本轮范围：只审计和规划，不实现业务代码

## 0. 结论摘要

当前仓库已经冻结 `ReproductionPort` 四阶段生命周期、四个 Tool Port、Pydantic v2 实验
Contract、FakeReproductionEngine、HTTP 调试 Router、MCP Registry 映射和一套隔离的 HTTP + SQLite
MVP。基础边界正确，Fake E2E 也稳定，不需要重新定义第二套 ReproductionPort。

但是，当前的“真实 MVP”仍是 `httpx.ASGITransport + FastAPI + SQLite + 进程内延迟`：没有
Playwright，也没有 Toxiproxy/mitmproxy。该实现位于 `integrations/timeout_retry_mvp`，把测试环境、
故障注入、浏览器替身和 Reproduction Engine 聚合在同一适配代码中，适合 Step 12 的隔离因果验证，
不应直接提升为通用 RealReproductionEngine。

第一阶段建议选择 **Playwright + Toxiproxy + Test Backend + SQLite Test Database**。领域/服务层只调用
现有 Tool Port，不 import Playwright/Toxiproxy SDK。Production 写操作与故障注入在第一阶段一律拒绝，
只允许 `sandbox`、`demo`、`test` 或 `isolated` 环境。

公共 Contract 可以支持一个兼容型 MVP，但不能完整表达并由 Runtime 持久化“实验中新产生的 Evidence、
用于后续 cleanup 的环境引用、cleanup 结果/错误”。第 18 节给出 `ICP-REP-001`。在该 Proposal 获得确认
前，可以编写测试和内部领域设计，但不应声称完整满足 Experiment Evidence Collection 与可恢复 Cleanup。

## 1. 当前 Reproduction 已有代码

### 1.1 模块模板

`src/ops_agent/reproduction/` 已有一致的 Engine 模块结构：

```text
reproduction/
  domain/
    config.py                 # ReproductionConfig(enabled, adapter_name)
    errors.py                 # 模块错误基类、禁用错误、依赖错误
  service/
    main.py                   # ReproductionService，稳定进程内入口
  ports/
    __init__.py               # 只重导出 canonical Ports
  adapters/
    fake.py                   # FakeReproductionEngine
  api/
    router.py                 # prepare/execute/verify/cleanup/health
    errors.py                 # ReproductionError -> ErrorResponse
```

`ReproductionService` 当前是薄应用层：检查模块是否启用，把未知异常统一映射为
`ReproductionDependencyError`，然后委托一个实现 `ReproductionPort` 的 Adapter。它没有实验编排、环境策略、
Verifier 或清理状态管理。

### 1.2 已有隔离 MVP

`src/ops_agent/integrations/timeout_retry_mvp/` 已经证明以下真实因果链：

- FastAPI 测试后端先写 SQLite 并 commit；
- 首次响应在 commit 后延迟；
- httpx 客户端超时并以相同 business ID 重试；
- 两个 request ID 产生两条订单记录；
- 请求、日志、SQLite、HTML/page event 被保存为 Artifact；
- Runtime 最终到达 `COMPLETED`。

可复用的是 Case 语义、测试后端行为、SQLite 判定规则、Artifact 命名和确定性验证条件。不可直接复用为
通用 Engine 的部分是 `HttpSqliteReproductionEngine` 对 `TimeoutRetryEnvironment` 的具体依赖，以及环境类内部
直接实现的响应延迟和 httpx 客户端重试。

## 2. FakeReproductionEngine 当前行为

`FakeReproductionEngine` 是确定性 `ReproductionPort` 实现：

| 方法 | 当前行为 |
|---|---|
| `prepare` | 返回固定 `FAKE-ENV-DUPLICATE-ORDER`，`ready=True` |
| `execute` | 可配置前 N 次抛异常；成功时固定返回首次成功、响应延迟、重试、两个订单 |
| `verify` | 只检查 `outputs["orders_created"] == 2`，确认固定 H-1 |
| `cleanup` | 固定返回 `cleaned=True`，无实际资源 |

优点是完全确定、Contract 合法、支持 Runtime retry 测试。局限是：

- 没有记录 prepare/cleanup 调用次数，无法证明异常分支一定 cleanup；
- cleanup 虽天然幂等，但没有状态断言；
- verify 只验证单个计数字段，未验证 request/trace/DB/browser 因果链；
- `evidence_ids` 引用既有调查证据，不产生实验 Evidence 对象；
- `fail_times` 只覆盖 execute，未覆盖 prepare、fault、browser、verify、cleanup。

Fake 必须继续保留，作为快速架构回归和真实工具不可用时的确定性替身。

## 3. 当前 ReproductionPort

canonical 定义位于 `src/ops_agent/ports/engines.py`，本模块只在
`src/ops_agent/reproduction/ports/__init__.py` 重导出：

```python
async def prepare(plan: ExperimentPlan) -> PreparedEnvironment
async def execute(request: ExperimentExecutionRequest) -> ExperimentResult
async def verify(request: ExperimentVerificationRequest) -> VerificationResult
async def cleanup(request: EnvironmentCleanupRequest) -> CleanupResult
```

所有方法均为 async，输入输出均为公共 Contract，没有 FastAPI、LangChain、Playwright 或供应商对象。
此接口应复用，禁止创建 `RealReproductionPort`、`ExperimentRunnerPort` 等竞争性上层 Port。

`ReproductionService` 自身结构上也满足 `ReproductionPort`，因此组合根可以注入
`ReproductionService(RealReproductionEngine(...), config)`，Runtime/Runner 不需要知道具体实现。

## 4. 当前 Tool Ports

canonical 定义位于 `src/ops_agent/ports/tools.py`：

| Port | 方法 | 当前 Contract |
|---|---|---|
| `BrowserToolPort` | `execute` | ExperimentExecutionRequest -> ExperimentResult |
| `ApiToolPort` | `execute` | ExperimentExecutionRequest -> ExperimentResult |
| `ShellToolPort` | `execute` | ExperimentExecutionRequest -> ExperimentResult |
| `FaultInjectionToolPort` | `apply` | ExperimentExecutionRequest -> ExperimentResult |
| `FaultInjectionToolPort` | `rollback` | EnvironmentCleanupRequest -> CleanupResult |

`src/ops_agent/integrations/mcp/reproduction/adapter.py` 已把这些 Port 映射为：
`browser_action`、`api_call`、`shell_execute`、`fault_inject`、`experiment_execute`、
`experiment_cleanup`。当前仅有 transport-neutral Registry 和 Fake Tool；没有 Reproduction MCP 的独立网络
transport，也没有 Playwright/Toxiproxy 实现。

这些 Tool Port 可以承载第一阶段 MVP，不新增第二套 Tool Port。缺点是每个低层动作都返回完整
`ExperimentResult`，Real Engine 必须把它视为“阶段结果”再聚合，而不能把任一 Tool 的返回值直接冒充整个
实验结果。后续若扩展多工具复杂实验，应单独提出 Tool Action Result Contract，而不是在本阶段私自改变 Port。

## 5. 当前 Experiment Contracts 审计

### 5.1 表达能力

| 需求 | 当前字段 | 结论 |
|---|---|---|
| experiment_id | Plan/Prepared/Result/Cleanup 均有 | 足够，需增加一致性校验 |
| hypothesis_id | `ExperimentPlan.hypothesis_ids` | 可通过 Plan 关联，Result 不自包含 |
| environment | `ExperimentPlan.environment`、PreparedEnvironment | 可表达，但环境类型未受枚举约束 |
| preconditions | environment/steps | 可约定表达，缺显式字段和 Schema |
| actions | `ExperimentPlan.steps` | 足够 |
| fault injection | steps/environment | 可约定表达，缺强类型 FaultSpec |
| expected_behavior | step.expected_outcome/success_criteria | 足够用于 MVP |
| success_criteria | `ExperimentPlan.success_criteria` | 足够 |
| actual_behavior | Result.observations/outputs | 足够 |
| evidence_refs | `ExperimentResult.evidence_ids` | 只能引用 ID，不能携带新 Evidence |
| execution status | `ExperimentResult.status` | 足够 |
| verification status | `VerificationResult.status` | 足够 |
| cleanup status | `CleanupResult.cleaned` | 只有 bool，没有被 IncidentState 持久化 |
| timestamps | Result 有 start/end；其他阶段只有通用 timestamp | 部分足够 |
| errors | TaskResult.error 或抛异常 | Result/Cleanup 自身没有结构化 errors |

### 5.2 命名差异

任务书提到的 `EnvironmentResult` 在代码中不存在；canonical 名称是 `PreparedEnvironment`。实施必须使用
`PreparedEnvironment`，不能新增同义 DTO。`CleanupResult` 已存在。

### 5.3 当前可行边界

第一阶段可以在不改公共接口的情况下，用以下约定完成“兼容替换型 MVP”：

- `environment` 必须包含 `kind`、test backend、database、browser、fault adapter 配置；
- precondition、expected behavior 由 `steps` 与 `success_criteria` 表达；
- Tool 阶段输出先在 Engine 内验证，再汇总为最终 `ExperimentResult`；
- 实际行为写入 `observations/outputs`；
- 失败通过 ReproductionError -> TaskResult.error 进入 Runtime retry/reflection；
- cleanup 通过现有 `CleanupResult` 返回。

这能满足 Port 替换和固定 Case，但不能完整满足“实验 Evidence 被 Runtime 接纳”和“重启后恢复 cleanup”。

## 6. 当前 Runtime 调用关系

Runtime 本身不调用 Engine；它只生成 `RuntimeTask`、接收 `TaskResult` 并按显式转换表推进：

```text
EXPERIMENT_PLAN --requires_approval--> WAITING_HUMAN -> REPRODUCE
EXPERIMENT_PLAN -------------------------------> REPRODUCE
REPRODUCE --succeeded--> VERIFY
REPRODUCE --failed status--> REFLECT
VERIFY --confirmed--> RCA
VERIFY --rejected/inconclusive--> REFLECT
```

当前 `FakeIncidentRunner` 在 `REPRODUCE` Task 内调用 `prepare -> execute`，在下一次 `VERIFY` Task 内调用
`verify -> cleanup`。这里存在两个真实化障碍：

1. cleanup request 的 environment ref 被硬编码为 `FAKE-ENV-DUPLICATE-ORDER`；
2. execute/verify 抛异常时没有跨阶段 finally-cleanup 保证。

Core Runtime 的转换表和 handler 不需要修改。第一阶段应在 Engine 的 lease/cleanup 防线及 task-owner integration
层解决：prepare 生成的 ref 必须随执行结果关联；prepare 部分失败、execute 失败、verify 失败时由 Engine 就地回滚；
正常路径由调用方显式 cleanup，重复调用安全。不能把 Playwright/Toxiproxy 调用写入 Runtime。

## 7. 当前缺失能力

- 通用 `RealReproductionEngine` 和工具编排器；
- 环境类型/写操作安全校验；
- 实验 session/lease 注册和 experiment/environment 关联；
- Playwright BrowserTool Adapter；
- Toxiproxy FaultInjectionTool Adapter；
- Test Backend 的受控 reset/query API Adapter；
- 真浏览器中的 timeout + retry 客户端行为；
- 确定性 Verifier；
- prepare 部分失败回滚、execute/verify 失败 cleanup、幂等 cleanup；
- Tool timeout 与失败分类；
- 实验 Evidence 对象的生产、校验和 Runtime 接纳；
- 真实 ReproductionPort contract kit；
- `FakeKnowledge + FakeReasoning + FakeInvestigation + RealReproduction` E2E；
- 一键启动/停止 Playwright + Toxiproxy + Test Backend Lab；
- 真实 Reproduction MCP transport 与授权。

## 8. Tool / Engine 边界污染审计

`src/ops_agent/reproduction/domain`、`service` 和 `ports` 当前没有 import Playwright、Toxiproxy、mitmproxy、
httpx、subprocess 或数据库 SDK，边界没有污染。

隔离 MVP 中 `HttpSqliteReproductionEngine` 直接依赖 `TimeoutRetryEnvironment`，后者直接使用 FastAPI、httpx、
SQLite 和 asyncio delay。它位于 `integrations/timeout_retry_mvp`，不是 Reproduction domain/service，因此没有违反
Core 依赖守护；但它是 Case-specific vertical slice，不应移动进 domain/service，也不应直接改名为
RealReproductionEngine。

## 9. Playwright / Toxiproxy 直接依赖审计

当前项目依赖中没有 `playwright`、Toxiproxy client 或 mitmproxy；源码中也没有这些 SDK import。
`docs/architecture/05-timeout-retry-mvp.md` 已明确记录二者未验证。

第一阶段引入后，SDK/HTTP 细节只能位于：

```text
reproduction/adapters/browser/
reproduction/adapters/fault_injection/
tests/fixtures/reproduction-lab/ 或 integrations/reproduction_lab/
```

domain、service、contracts、ports、core 不得 import 它们。

## 10. RealReproductionEngine 建议结构

在保留现有模板的基础上做最小扩展：

```text
src/ops_agent/reproduction/
  domain/
    config.py
    errors.py
    environment_policy.py       # 环境 allowlist、production 拒绝
    experiment_session.py       # 内部 Pydantic value object，不跨模块
  service/
    main.py                     # 保留 ReproductionService
    reproduction_engine.py      # RealReproductionEngine，实现 ReproductionPort
    experiment_runner.py        # Tool Port 顺序编排、timeout、结果聚合
    verifier.py                 # 纯确定性判定
    cleanup_manager.py          # 逆序补偿、幂等清理
  ports/
    __init__.py                 # 继续只重导 canonical Ports
  adapters/
    fake.py
    browser/playwright.py       # BrowserToolPort
    fault_injection/toxiproxy.py# FaultInjectionToolPort
    api/test_backend.py         # ApiToolPort，仅实验 Lab 控制面
  api/                          # 保留现有 debug router
```

依赖注入建议：

```text
ReproductionService
  -> RealReproductionEngine
       -> EnvironmentPolicy
       -> ExperimentRunner
            -> BrowserToolPort
            -> ApiToolPort
            -> FaultInjectionToolPort
       -> DeterministicVerifier
       -> CleanupManager
```

ShellToolPort 保留扩展点但第一阶段不注入真实 destructive shell。Real Engine 构造器接收 Ports 和配置，不自行
构造具体 Adapter；具体装配只放 bootstrap 或 MVP Lab composition root。

## 11. Verifier 设计

Verifier 是无 LLM 的纯确定性组件。输入只来自 `ExperimentVerificationRequest` 和经过 Adapter 标准化的结果，
不得查询模型或根据自由文本“感觉”确认。

固定 Case 的全部必需谓词：

1. Plan、PreparedEnvironment、ExperimentResult 的 incident/experiment ID 一致；
2. 目标 hypothesis 包含 `H-1`；
3. browser events 严格包含 `submit -> timeout -> retry -> success`；
4. 恰好两个 POST create 请求；
5. 两个请求 business ID、trace ID 相同，request ID 不同；
6. 首次请求在响应延迟前已经完成数据库 commit；
7. 首次响应延迟大于 client timeout；
8. 第二次请求再次创建成功；
9. SQLite 中同一 business ID 恰好两条订单；
10. Result 引用的 Evidence/Artifact 均存在且 correlation 一致。

判定规则：全部必需谓词成立为 `CONFIRMED`；存在反证为 `REJECTED`；必需资料缺失、工具失败或无法可靠判定为
`INCONCLUSIVE`。`confidence` 使用固定规则计算，不允许 Adapter 任意声称 1.0。Verifier 只返回
`VerificationResult`，不修改 Hypothesis 或 IncidentState。

## 12. Cleanup 设计

CleanupManager 按资源获取的逆序执行补偿：

```text
stop/close browser context
-> remove Toxiproxy toxic / restore proxy
-> reset test backend data
-> release experiment lease
```

具体要求：

- prepare 每成功获得一个资源就登记补偿动作；中途失败立即回滚已获得资源；
- execute 失败或 timeout 立即 cleanup；
- verify 失败也 cleanup；
- 正常 verify 后显式 cleanup；
- cleanup 使用 `(experiment_id, environment_ref)` 做幂等键；
- 已清理再次调用返回 `cleaned=True` 并说明 already-cleaned；
- 一个补偿失败时仍继续执行其余补偿，最后聚合错误；
- Toxiproxy toxic 必须使用本次实验唯一名称，不能删除其他实验 toxic；
- 测试证据目录可以只读保留，但活动浏览器、代理规则和数据库测试数据必须释放/重置。

第一阶段 Engine 内存 session registry 只服务单进程 Lab；跨进程恢复依赖后续持久化 lease，不在本阶段冒充已支持。

## 13. Tool Adapter 设计

### 13.1 Playwright Adapter

实现 `BrowserToolPort.execute`，只解释经过 Real Engine 校验的固定动作 profile。它负责启动隔离 browser context、
打开 Test Backend 页面、点击创建、等待 timeout/retry/success DOM 状态，并输出标准 Result/Artifact。它不判断根因，
不读取 Product Skill，不修改 Runtime。

### 13.2 Toxiproxy Adapter

第一阶段选择 Toxiproxy，而不是 mitmproxy，原因是 toxic 创建/删除 API 简单、作用域可按 proxy/toxic name 隔离、
回滚易做成幂等。Adapter 实现 `FaultInjectionToolPort.apply/rollback`，只为本实验建立 downstream latency toxic。
领域/service 不知道 Toxiproxy HTTP API。

### 13.3 Test Backend API Adapter

实现 `ApiToolPort.execute`，只调用 Lab 控制面完成 health、reset、查询 request records 和查询订单结果。禁止通过
Shell 或人工 SQL 修改数据来制造成功结果。数据库 reset 是 prepare/cleanup 的 Lab 管理动作，实验中的两条订单必须
由页面触发的真实 API 请求产生。

### 13.4 Shell Adapter

第一阶段不实现真实 ShellTool Adapter。Port 保留；未来必须有 command allowlist、工作目录隔离、timeout、输出上限、
凭据脱敏和生产禁用，不能接受 ExperimentPlan 中的任意字符串直接拼接 shell。

## 14. MVP Lab 设计

建议独立测试 Lab，不把 Test Backend 放进 Reproduction domain：

```text
tests/fixtures/reproduction-lab/
  backend/                     # 非幂等订单 Test Backend + 页面
  compose.yml                  # Test Backend + Toxiproxy（若采用容器）
  README.md

Test browser
  -> Toxiproxy
  -> Test Backend
  -> SQLite test database
```

页面 JavaScript 使用 AbortController/timeout 触发一次受控重试。后端每个 POST 都先 commit，再返回响应。Toxiproxy
只延迟首次实验窗口中的响应路径，第二次请求正常返回。具体实现必须验证 Toxiproxy latency 方向和作用范围；如果
Toxiproxy 无法只延迟首个响应，则由 Lab 提供一次性路由/连接并为每次尝试使用独立 proxy，而不是把延迟逻辑重新
写回 Engine。

一键生命周期：

```text
setup lab -> health check -> reset -> prepare data -> apply toxic
-> Playwright action -> collect artifacts -> deterministic verify
-> remove toxic -> reset/cleanup -> stop lab
```

同一命令连续运行两次必须得到相同业务结论和独立 experiment/artifact ID。

## 15. 需要新增或修改的文件

### 15.1 先写测试

```text
tests/reproduction/test_prepare.py
tests/reproduction/test_execute.py
tests/reproduction/test_verify.py
tests/reproduction/test_cleanup.py
tests/reproduction/test_cleanup_on_failure.py
tests/reproduction/test_idempotent_cleanup.py
tests/reproduction/test_timeout_retry_duplicate_case.py
tests/reproduction/test_invalid_environment.py
tests/reproduction/test_fault_injection_failure.py
tests/reproduction/test_real_reproduction_port_contract.py
tests/e2e/test_real_reproduction_incident_flow.py
```

### 15.2 最小实现

- 新增第 10 节列出的 domain/service/adapter 文件；
- 更新 `reproduction/adapters/__init__.py` 导出明确的 Real/Adapter 入口；
- 扩展 `ReproductionConfig`，但只增加部署必需且有测试的字段；
- 在 bootstrap/MVP composition root 注入真实 Adapter；
- 将现有 timeout-retry Case 可复用的测试语义迁移到 Lab Adapter，保留旧 Case 回归；
- 对 `FakeIncidentRunner` 的硬编码 environment ref 和 cleanup finally 做最小通用化，禁止加入工具逻辑；
- 更新 `docs/modules/06-reproduction.md` 和新增 Lab 使用说明；
- 如 ICP 获批，再按第 18 节调整 Contracts、示例、Contract tests 和 Runtime result acceptance。

## 16. 明确不能修改的文件/边界

第一阶段不得破坏或改写：

- `CoreRuntime.STATE_TRANSITIONS`、REPRODUCE/VERIFY/REFLECT 语义；
- canonical `ReproductionPort` 方法名与四阶段生命周期；
- Knowledge、Reasoning、Investigation 的实现；
- FakeKnowledge/FakeReasoning/FakeInvestigation 的固定行为；
- Built-in `reproduction-planning` 的方法论边界；
- Product Skill、Skill Runtime 和 CodeBuddy Plugin；
- 现有 Fake E2E 的权威 IncidentState 流程；
- Runtime MCP 的五个 Core 工具；
- 真实产品知识或 V7R2 外部资产。

公共 Contract/Tool Port 若要改，只能在 ICP 获批后做向后兼容修改和完整 Contract 回归。

## 17. 测试计划

按 AGENTS.md 顺序：先写失败测试，再做最小实现。

| 测试 | 关键断言 |
|---|---|
| prepare | reset 完成、环境 ready、ID 对应、部分失败回滚 |
| execute | fault -> browser -> collect 顺序；两个请求/订单 |
| verify | 全部确定性谓词；confirmed/rejected/inconclusive |
| cleanup | fault/browser/data 均释放 |
| cleanup on failure | prepare/fault/browser/timeout/verify 每个失败点都 cleanup |
| idempotent cleanup | 连续两次 cleanup 安全且无跨实验影响 |
| invalid environment | production 写/故障注入明确拒绝 |
| fault failure | 不启动 browser 或在失败后补偿 |
| timeout | Adapter deadline 生效，错误 retryable 分类正确，资源释放 |
| correlation | incident/request/experiment/hypothesis/environment ref 不串线 |
| Contract schema | 所有输入输出可 validate/dump/json/schema |
| Port contract | RealReproductionEngine/ReproductionService 均满足 Protocol |
| independent lab | 一键 setup/run/verify/cleanup，可连续运行两次 |
| E2E replacement | 仅把 FakeReproduction 替换为 Real，其余三 Engine 和 Runtime 不变 |

建议验证命令：

```bash
pytest tests/reproduction -q
pytest tests/contracts -q
pytest tests/core -q
pytest tests/e2e/test_fake_incident_flow.py -q
pytest tests/e2e/test_real_reproduction_incident_flow.py -q
pytest tests/e2e/test_timeout_retry_duplicate_create.py -q
pytest tests/integration/mcp -q
ruff check .
ruff format --check .
mypy
pytest
git diff --check
```

真实 Playwright/Toxiproxy 验收还必须记录其版本、启动命令、容器状态、浏览器版本和 Artifact 路径，不能只依赖 Mock。

## 18. Interface Change Proposal：ICP-REP-001

### 18.1 缺失内容

当前接口缺少三项跨阶段必需事实：

1. `ExperimentResult` 只能给出 `evidence_ids`，不能携带实验中新产生的标准 `Evidence`；
2. prepare 的 `environment_ref` 不进入 IncidentState/ExperimentResult，后续 cleanup 只能依赖进程内状态或硬编码；
3. `CleanupResult` 不进入 `IncidentState`，也没有结构化错误/开始结束时间，无法审计清理是否完成。

### 18.2 为什么 metadata/outputs 不足

- Evidence 需要 Pydantic schema、raw reference、digest、hypothesis 支持/反驳关系和 acquisition status；放进任意
  `outputs` 会绕过 Evidence Validator，也不能被 Runtime Evidence Graph 接纳；
- environment ref 是资源释放能力标识，放在 metadata 会变成无约束字符串且没有生命周期语义；
- cleanup/error 是安全与审计事实，不应依赖各 Adapter 自定义 key；
- metadata 来自调用方，不能作为“已获人工批准”这种安全授权证明。

### 18.3 建议字段/类型

优先采用向后兼容的可选扩展：

- `ExperimentResult.environment_ref: NonEmptyString | None = None`；
- `ExperimentResult.hypothesis_ids: list[HypothesisId] = []`，并校验是 Plan 子集；
- `ExperimentResult.evidence: list[Evidence] = []`，`evidence_ids` 必须与内嵌 Evidence 对应；
- `CleanupResult.started_at/completed_at: AwareDatetime | None = None`；
- `CleanupResult.errors: list[ErrorResponse] = []`；
- `IncidentState.cleanup_results: list[CleanupResult] = []`；
- Runtime `_apply_reproduction` 接纳并追加内嵌实验 Evidence，cleanup task/result 的持久化方式需由 Runtime Owner 确认。

若 Runtime Owner 不接受把 Evidence 嵌入 ExperimentResult，则替代方案是新增
`ReproductionExecutionOutcome(result, environment, evidence)`，并让 `TaskOutput` 使用该 aggregate；不要同时采用两套。

### 18.4 optional 与兼容性

建议新增字段全部带默认值，旧 JSON 和 Fake 保持可读取。但由于 v1 `extra="forbid"` 且文档声明 Frozen，即使是可选
字段也必须走正式 Contract 评审、JSON Schema/示例更新，不能直接提交。

### 18.5 对其他模块的影响

- Runtime：接纳实验 Evidence、保存 cleanup 结果；状态转换不变；
- Reasoning/Reflection：可读取已接纳的实验 Evidence，不读取工具原始对象；
- RCA：可把实验 Evidence 纳入证据链；
- Investigation：无实现依赖，只共享 Evidence Contract；
- Agent/External Adapter：需允许新增默认字段，但无需生成它们；
- Fake：补充默认环境引用和可选 Evidence，行为不变。

### 18.6 Contract Test 变化

- JSON round trip 与 JSON Schema；
- experiment/incident/request/hypothesis/evidence ID correlation；
- Evidence ID 不重复、不悬空；
- completed_at 不早于 started_at；
- cleanup errors 与 cleaned 状态一致性；
- 旧 v1 fixture 兼容读取；
- Runtime 接纳后 Evidence/Cleanup 在 IncidentState 可见。

### 18.7 本阶段安全授权说明

`ExperimentExecutionRequest` 当前没有不可伪造的 approval proof。第一阶段不增加 token 字段，而是只允许隔离环境，
对 production/high-risk 写操作无条件拒绝。未来允许高风险环境前需另行设计 Runtime 签发的授权能力；不能用 metadata
或 `requires_approval=True` 冒充已经批准。

## 19. 独立验收方式

不经过完整 Incident 时，使用测试 composition root：

1. 启动 Test Backend、SQLite、Toxiproxy；
2. 构造标准 ExperimentPlan；
3. `prepare` 并断言数据库为空、toxic 只属于本 experiment；
4. `execute`，由 Playwright 点击一次；
5. `verify`，断言两个 request、两个 order、同一 business/trace；
6. `cleanup` 两次，均安全；
7. 再执行整套流程，结果仍一致；
8. 模拟每个失败点，检查 proxy/browser/data 没有残留。

独立验收不得直接 UPDATE/INSERT 数据库制造重复订单；SQLite 只接受 reset 和查询，订单只能由 Test Backend API 创建。

## 20. E2E 替换验证方式

新增 E2E 的组合必须严格为：

```text
CoreRuntime（原实现）
+ FakeKnowledgeEngine
+ FakeReasoningEngine
+ FakeInvestigationEngine
+ ReproductionService(RealReproductionEngine + real Lab Tool Adapters)
```

测试只通过构造器替换 `reproduction` 依赖，不修改 IncidentState，不跳 Stage，不改 Runtime transition table。最终断言：

- Stage 历史包含 REPRODUCE -> VERIFY -> RCA -> COMPLETED；
- ExperimentPlan/Result/Verification 的 EXP/H ID 一致；
- 两个真实请求和两条 DB 记录；
- verification 为 CONFIRMED；
- cleanup 已执行且可重复；
- 原 `tests/e2e/test_fake_incident_flow.py` 完全不回退。

现有 FakeReasoning 的 Plan 使用 `environment={kind: fake, external_systems: false}`。为严格满足替换验收，E2E 必须保留
该 FakeReasoningEngine，不得换成另一个 Plan fixture。MVP composition config 可把 `fake` 声明为 `isolated` 的安全别名，
并绑定到唯一允许的 timeout-retry Lab profile；这种映射是部署配置，不是产品知识。Real Engine 仍须校验
`external_systems=false`、risk/approval 和受支持步骤，不能根据 Incident title 猜测工具参数，也不能把任意 action 文本直接
翻译成 Shell/Playwright/Toxiproxy 指令。

## 21. 风险与未验证项

### 风险

1. **公共接口缺口**：实验 Evidence、environment ref、cleanup audit 尚未进入 Runtime 权威状态；见 ICP-REP-001。
2. **cleanup owner 不清晰**：当前调用方跨 REPRODUCE/VERIFY 管理生命周期，异常时可能泄漏资源。
3. **安全策略未实现**：`core/policies` 仍是 placeholder，`risk_level` 是自由字符串；当前仅有
   `requires_approval` 跳转。
4. **直接 HTTP debug 绕过**：Reproduction Router/MCP 能直接调用高风险方法，当前没有认证/授权；真实 Adapter 上线前必须
   默认禁用或限制到隔离 Lab。
5. **Tool Port 粒度较粗**：低层工具返回完整 ExperimentResult，复杂编排时容易混淆阶段结果和最终结果。
6. **Toxiproxy 首次响应范围**：需要实测 downstream latency 是否能精确覆盖首次响应而不延迟 retry；可能需要每次实验独立
   proxy/连接切换。
7. **浏览器稳定性**：Playwright 安装、浏览器版本、CI 共享内存和 timeout 会影响可重复性。
8. **并发隔离**：固定 proxy name、business ID、SQLite 路径会导致并发实验串扰，必须引入 experiment-scoped namespace。
9. **现有 MVP 分层债务**：Step 12 vertical slice 混合多种能力，迁移时必须保留旧回归，避免大规模重写。
10. **持久化缺失**：进程重启后 session/lease 丢失，无法自动回收未清理资源。

### 未验证项

- Playwright 和浏览器尚未安装/运行；
- Toxiproxy/mitmproxy 尚未安装/运行，本计划选择尚未实测；
- 没有真实 Reproduction MCP 网络 transport；
- 没有验证生产或远程环境，且第一阶段明确禁止；
- 没有验证高风险 Human Approval 的不可伪造授权；
- 没有验证并发实验、跨进程恢复、长期 lease 回收；
- 没有验证 k6、Chaos Mesh、K8s/MQ/CPU/Memory/Clock fault；
- 没有验证真实产品/V7R2；
- 当前专项基线仅验证既有实现：`63 passed`，未包含本计划中的新真实工具。

## 22. 建议实施顺序与 MVP Done 标准

实施顺序：

1. 评审并确认 ICP-REP-001 的采用、缩减或延期决定；
2. 写安全策略、Port contract、prepare/cleanup 失败测试；
3. 实现纯领域 policy、session、verifier、cleanup manager；
4. 用确定性 Fake Tool Ports 完成 RealReproductionEngine 单元闭环；
5. 修正 task-owner 中硬编码 environment ref 和异常 cleanup，不改 Runtime 状态机；
6. 建 Test Backend + SQLite Lab；
7. 实现 Toxiproxy Adapter 并验证作用域/rollback；
8. 实现 Playwright Adapter；
9. 跑独立真实 Case，两次重复执行；
10. 跑 RealReproduction 替换 E2E；
11. 跑 Contract/Core/Fake E2E/MCP/全量静态与回归；
12. 更新模块文档和真实验证记录。

第一阶段 Done 必须同时满足：

- RealReproductionEngine 结构上实现既有 ReproductionPort；
- domain/service 不依赖 Playwright/Toxiproxy SDK；
- 只允许隔离测试环境，production 写/故障注入被拒绝；
- prepare/execute/verify/cleanup 均有正常与失败测试；
- 所有失败路径 cleanup，cleanup 幂等；
- Playwright + Toxiproxy + Test Backend + SQLite 真实运行；
- 固定 Case 产生两个请求、两个订单和可追踪 Artifact/Evidence；
- Verifier 确定性确认 H-1；
- FakeKnowledge + FakeReasoning + FakeInvestigation + RealReproduction 经原 Runtime 到达 COMPLETED；
- Fake E2E、现有 HTTP+SQLite MVP、Contract、Core、MCP 和全量测试不回退；
- ruff、format、mypy、pytest、git diff check 全部通过。
