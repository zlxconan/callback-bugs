# Module Dependency Rules

> 状态：Architecture baseline  
> 日期：2026-09-15

## 1. 模块调用方向

```text
API / CLI / Agent Host
          |
          v
      RuntimePort
          |
          v
      Core Runtime ---------------> StateRepositoryPort ---> Persistence Adapter
          |
          +---> KnowledgePort -----> Knowledge Service -----> Knowledge Tool Ports/Adapters
          |
          +---> ReasoningPort -----> Reasoning Service
          |
          +---> InvestigationPort -> Investigation Service -> Observation Tool Ports -> MCP/Adapters
          |
      +---> ReproductionPort --> Reproduction Service --> Execution Tool Ports ---> MCP/Adapters

Knowledge Adapter --> Generic Skill Runtime --> installed Product Plugin

All arrows carry Pydantic Contracts.
```

Runtime 是唯一跨 Engine 编排者。箭头表示编译时依赖抽象或运行时调用方向，不表示 Engine 实现之间可相互 import。

## 2. 允许依赖

| 模块 | 允许 import |
|---|---|
| `contracts` | Python 标准库、Pydantic v2 |
| `ports` | Python 标准库、`contracts` |
| `core/domain` | Python 标准库、`contracts`、`ports` |
| `core/runtime` 实现 | `contracts`、`ports`、core 内部领域规则 |
| Engine `domain` | Python 标准库、`contracts`、本 Engine domain |
| Engine `service` | `contracts`、顶层 `ports`、本 Engine domain/ports |
| Engine `ports` | 顶层 `ports` 的对应 Protocol 重导出 |
| Engine `adapters` | `contracts`、`ports`、本 Engine API/domain；必要时允许 SDK/LangChain |
| `integrations` | `contracts`、`ports`、外部 SDK/LangChain/MCP client |
| `skill_runtime` | Python 标准库、Pydantic；不得依赖 Engine 实现或具体产品内容 |
| 外部 `api` | FastAPI、`contracts`、`RuntimePort`/application facade |
| `bootstrap` | 所有需要装配的抽象与具体实现；这是唯一组合根 |

## 3. 禁止依赖

- `contracts` 或 `ports` import FastAPI、LangChain、MCP SDK、ORM 或具体 Adapter。
- `contracts/core/domain` import LangChain。
- Core Runtime import 任意 Engine Service/Adapter 实现。
- Core Runtime import 或读取具体 Product Skill Plugin；插件解析只发生在 Knowledge Adapter 边界。
- 一个 Engine 的 domain/service/adapter import 另一个 Engine 的实现。
- Reasoning Service 调用 Investigation 或 Reproduction 实现。
- Reasoning 读取 Product Skill manifest、入口文件或 Repository。
- Investigation/Reproduction 直接写 `IncidentState` 或调用 `StateRepositoryPort` 绕过 Runtime。
- Engine 或 Agent Host 直接推进全局工作流状态。
- API 将 FastAPI Request/Response 对象传入 Runtime/Engine Port。
- Tool Port 返回供应商 SDK object、LangChain message、HTTP response 或任意字典。
- Adapter 反向依赖 bootstrap，或在业务模块内自行构造其他具体 Adapter。

禁止示例：

```text
ReasoningService -> InvestigationService.collect(...)
Runtime -> ConcreteKnowledgeService(...)
contracts -> langchain_core.messages.BaseMessage
InvestigationService -> SqlIncidentRepository.save(...)
```

正确示例：

```text
ReasoningPort.plan_evidence(...) -> EvidencePlan
Runtime validates/accepts EvidencePlan
Runtime -> InvestigationPort.collect_batch(EvidencePlan)
InvestigationPort -> EvidenceBatch
Runtime validates/updates IncidentState
```

## 4. Contract 生产与消费矩阵

| Contract | 主要生产者 | 主要消费者 |
|---|---|---|
| `ProblemContext` | Inbound API/Agent Host | Runtime、全部 Engine |
| `ProductContext` | Knowledge | Runtime、Reasoning、Reproduction |
| `KnowledgeContext` | Knowledge | Runtime、Reasoning |
| `TroubleshootingContext` | Knowledge/Inbound | Runtime、Reasoning、Reproduction |
| `Hypothesis` / `HypothesisSet` | Reasoning | Runtime、Investigation、Reproduction |
| `EvidenceRequest` / `EvidencePlan` | Reasoning | Runtime、Investigation |
| `Evidence` / `EvidenceBatch` | Investigation/Reproduction | Runtime、Reasoning、Verifier |
| `ExperimentPlan` | Reasoning | Runtime、Reproduction、Policy |
| `PreparedEnvironment` | Reproduction | Runtime、execution tools |
| `ExperimentResult` | Reproduction/tool Adapter | Runtime、Reasoning、Verifier |
| `VerificationResult` | Reproduction Verifier | Runtime、Reasoning、RCA generation |
| `ReflectionResult` | Reasoning | Runtime |
| `RootCauseAssessment` | Reasoning | Runtime、RCA generation |
| `IncidentState` | Runtime | Repository、API、Agent Host |
| `RuntimeTask` | Runtime | Engine/Agent execution boundary |
| `TaskResult` | Engine/Agent execution boundary | Runtime |
| `RCAReport` | Runtime/RCA renderer | API、Agent Host、operator |
| `ErrorResponse` | Validator/Policy/Runtime/Engine/Adapter | Runtime、API、Agent Host |
| `AuditEvent` | Runtime/controlled boundary | StateRepository/Audit sink |
| `CleanupResult` | Reproduction/Fault Adapter | Runtime |

生产者只能提出或返回 Contract。除 Runtime 外，任何模块都不能因为产生 Contract 而直接修改全局 Incident State。

## 5. 源码布局与接口所有权

- `ops_agent.ports` 是唯一 canonical Protocol 定义位置。
- `ops_agent.<engine>.ports` 只重导出该 Engine 使用的 canonical Protocol，不能再次定义同名接口。
- `ops_agent.core.runtime` 重导出 `RuntimePort`；未来 Runtime 实现放在 core/runtime 内，但通过组合根绑定。
- `ops_agent.core.state` 重导出 `StateRepositoryPort`。
- Investigation 与 Reproduction 的 tool ports 分别在本 Engine ports package 暴露，但定义仍位于顶层 canonical package。

该安排让 Runtime 只 import `contracts + ports`，同时让 Engine package 有清晰的本地公共入口。

## 6. 自动验证

架构测试验证：

- 顶层 Ports 除标准库外只能 import `ops_agent.contracts` 或自身聚合模块。
- 四个 Engine 的 ports package 不定义竞争 Protocol。
- 所有 Port 都是 runtime-checkable Protocol。
- 所有方法均为 async，存在返回注解，且签名不直接出现 `Any`、`dict`、FastAPI 或 LangChain。
- Engine 之间不存在实现 import。
- Runtime、Reasoning、Knowledge、Investigation、Reproduction、Repository 和全部 Tool Port 都可被确定性 Fake 结构实现。
