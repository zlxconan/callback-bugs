# AI 辅助网上问题分析与复现 Agent：架构实施计划

> 文档状态：初始架构准备（Step 0）  
> 日期：2026-09-15  
> 本阶段范围：仅仓库审查与架构规划，不包含业务实现、依赖安装或框架引入。

## 1. 项目理解

本项目要构建一套与具体 Agent/LLM 解耦的线上问题分析与自动复现能力。系统不是让大模型直接、无约束地调用工具，而是将职责拆分为四类专业 Engine、一个唯一编排 Runtime、稳定的 Contracts/Ports，以及可替换的 Agent Host 和执行适配器。

核心职责边界如下：

- **Skill**：定义某类产品或故障“应该如何分析”的可版本化知识与方法，不保存运行态。
- **Agent/LLM**：基于当前上下文做候选选择、规划、假设生成和反思；其输出必须经过结构化校验，不能直接改变权威状态。
- **Core Runtime**：唯一流程编排者，持有工作流状态、预算、策略、重试、超时、循环控制和审批状态，并决定哪些动作可以执行。
- **MCP/Tool Adapter**：执行实际外部能力并返回结构化结果，不承担编排决策。
- **Engine**：封装一个问题域内的能力；Engine 之间不引用彼此实现，只通过 Contracts 与 Ports 被 Runtime 协调。

首选落地形态是单进程、单部署单元的模块化单体。模块边界从第一天保持清晰，使未来能够把某个 Engine 或 Adapter 拆成独立服务，而不改变公开 Contract。

## 2. 仓库审查结果

检查时仓库状态如下：

- 当前分支为 `main`，Git 提示 `No commits yet`。
- `origin/main` 当前显示为 `gone`。
- 工作区除 `.git/` 外无项目文件。
- 根目录不存在 `AGENTS.md`，因此没有可读取或执行的仓库级附加规范。
- 不存在 README、docs、`pyproject.toml`、源码、测试、配置或 CI 文件。
- 不存在可复用的现有代码、Contract、测试夹具或文档。

因此本方案以用户给出的目标、技术栈强约束和开发规范为唯一项目基线。本步骤不从相邻仓库继承 `AGENTS.md`，因为相邻目录的规范不适用于当前仓库。

## 3. 架构决策

### 3.1 总体架构

```text
Agent Host / HTTP Client / CLI
              |
        Inbound Adapters
              |
       Core Runtime (唯一编排者)
       /       |        |       \
Knowledge  Reasoning  Investigation  Reproduction
 Engine     Engine        Engine         Engine
       \       |        |       /
          Contracts + Ports
                  |
          Outbound Adapters
  LLM/LangChain, MCP, DB, Obsidian, K8s,
  Trace/Logs/Metrics, Playwright, Shell, k6...
```

请求先进入 Inbound Adapter，由 Runtime 创建或恢复 Incident/Workflow 状态。Runtime 根据状态和策略调用 Engine Port；Engine 只返回结构化建议、证据需求或实验计划。Runtime 校验输出、执行审批和预算判断后，才允许通过 Tool Port 调用外部能力。外部结果标准化为 Contract，再写入权威状态与 Evidence Graph。

### 3.2 依赖规则

允许的依赖方向：

```text
contracts  <- ports <- runtime <- inbound adapters / bootstrap
     ^          ^         |
     |          |         +---- coordinates engines through ports
     +----------+-------------- engine implementations
     ^          ^
     +----------+-------------- outbound adapters
```

强制规则：

1. `contracts` 仅依赖 Python 标准库与 Pydantic v2；不依赖 LangChain、FastAPI 或具体基础设施。
2. `ports` 仅依赖标准库、typing 与 `contracts`；定义 Protocol/ABC，不放实现。
3. `domain` 仅依赖标准库、Pydantic v2 和 `contracts`；不依赖 FastAPI、LangChain、数据库或 MCP SDK。
4. `runtime` 仅依赖 `contracts`、`ports`、`domain`；不得依赖 LangChain、FastAPI 或任何 Engine 实现。
5. 每个 Engine 实现仅依赖 `contracts`、`ports`、`domain` 及自己的内部模块；禁止 import 其他 Engine 实现。
6. LangChain 只能出现在 LLM、Agent、Tool Adapter 实现内。
7. FastAPI 只能出现在 API/Inbound Adapter 与装配层内。
8. 具体实现的绑定只发生在 `bootstrap` 组合根；业务模块不得自行构造具体 Adapter。
9. 跨模块公共数据一律使用 Pydantic v2 Model；模块内部纯算法可使用不可变值对象，但越过边界前必须转换为公共 Model。
10. 架构依赖规则应由测试扫描 import AST 持续验证，避免仅依赖代码评审。

### 3.3 Contracts 设计

Contracts 是未来拆服务时保持不变的协议面，应按领域语义而非按传输协议组织，并从第一版就进行版本管理。

建议的核心模型：

- `Incident`：问题身份、产品、版本、环境、症状、严重度、时间范围和当前状态。
- `WorkflowRun` / `WorkflowStep`：运行 ID、状态、尝试次数、截止时间、预算和终止原因。
- `ProductContext` / `KnowledgeQuery` / `KnowledgeResult`：产品版本事实、预期行为、适用 Skill 和来源。
- `Hypothesis`：假设、置信度、支持/反对证据、可证伪条件和状态。
- `InvestigationPlan` / `EvidenceRequest`：需要获取的证据、理由、数据源、时间窗、成本与敏感级别。
- `Evidence` / `EvidenceRef` / `EvidenceRelation`：来源、采集时间、完整性、摘要、原始对象引用和图关系。
- `ReproductionPlan` / `Experiment` / `FaultInjection`：环境要求、步骤、变量、风险、审批要求与回滚说明。
- `ExecutionResult` / `VerificationResult`：输出引用、断言、成功标准、失败分类和可重复性。
- `DecisionRequest` / `DecisionResponse`：给 Agent/LLM 的有限候选、结构化选择、理由和置信度。
- `ApprovalRequest` / `ApprovalDecision`：审批范围、风险、过期时间、批准人和不可篡改关联 ID。
- `PolicyDecision` / `ToolCall` / `ToolResult`：允许、拒绝或要求审批，以及标准化执行结果。
- `DomainEvent`：只描述已发生事实，携带 schema version、correlation ID、causation ID 和时间戳。

Contract 约定：

- 使用严格字段、显式枚举、UTC 时间、稳定 ID 和 `extra="forbid"`。
- 对外 Contract 带 `schema_version`；破坏性变更新增版本，不原地改变语义。
- 大体积日志、Trace、录屏等不内嵌，使用内容摘要、哈希和受控对象引用。
- LLM 文本永远不是权威状态；必须解析为 Contract 并通过 Schema Validator。
- 错误应分类为 validation、policy、transient、timeout、dependency、user-action-required 和 terminal，供 Runtime 决定后续动作。

### 3.4 Ports 设计

建议定义以下稳定端口：

- Engine ports：`KnowledgePort`、`ReasoningPort`、`InvestigationPort`、`ReproductionPort`、`VerificationPort`。
- 决策端口：`DecisionProviderPort`，统一 Codex/CodeBuddy、自研 Agent 和 Fake 决策器。
- 工具端口：`ToolExecutorPort`、`ToolCatalogPort`；MCP 是主要实现，但不是 Runtime 的直接依赖。
- 状态端口：`IncidentRepositoryPort`、`WorkflowRepositoryPort`、`EvidenceRepositoryPort`、`ArtifactStorePort`。
- 知识端口：`KnowledgeSourcePort`、`SkillRegistryPort`、`ProductVersionResolverPort`。
- 观测端口：`TraceSourcePort`、`LogSourcePort`、`MetricsSourcePort`、`KubernetesPort`、`ChangeHistoryPort`、`ServiceGraphPort`。
- 实验端口：`EnvironmentProvisionerPort`、`BrowserAutomationPort`、`ApiClientPort`、`ShellPort`、`LoadGeneratorPort`、`NetworkFaultPort`、`ChaosPort`。
- 治理端口：`PolicyPort`、`ApprovalPort`、`ClockPort`、`IdGeneratorPort`、`AuditSinkPort`。

端口方法应以 Contract 为输入输出，并明确幂等键、deadline、取消语义和错误分类。禁止把 LangChain message、FastAPI request、Kubernetes SDK object 或 MCP 原始响应泄漏到端口之外。

### 3.5 Core Runtime

Runtime 建议采用显式状态机 + command/event 模式，不采用 LangChain workflow 对象。参考状态：

```text
RECEIVED
  -> CONTEXTUALIZING
  -> PLANNING
  -> INVESTIGATING
  -> [REFLECTING -> INVESTIGATING] (有界循环)
  -> REPRODUCTION_PLANNING
  -> [WAITING_APPROVAL]
  -> REPRODUCING
  -> VERIFYING
  -> RESOLVED | INCONCLUSIVE | FAILED | CANCELLED
```

Runtime 的关键职责：

- 校验每次状态转换是否合法，并以乐观锁或版本号防止并发覆盖。
- 为每次运行设置总 deadline、步骤 timeout、重试次数、LLM/tool 调用预算和反思循环上限。
- 将重试限制在明确的瞬时错误；副作用调用必须提供幂等键。
- 在 Shell、故障注入、生产环境访问、敏感数据读取等动作前执行 Policy；必要时进入 `WAITING_APPROVAL`。
- 保存 command、event、policy decision、approval 与 tool result 的审计链。
- 支持取消、恢复、重放和从中断点继续，但重放不得重复危险副作用。
- 统一调度 Engine；任何 Engine 不得自行形成跨 Engine 工作流。

### 3.6 Evidence Graph 所有权

目标描述在 Investigation Engine 和 Core Runtime 中都提到 Evidence Graph，存在潜在职责重叠。建议明确：

- Runtime/Domain 持有 Evidence Graph 的权威模型、版本、完整性约束和持久化事务。
- Investigation Engine 负责采集、标准化证据，并提出节点/关系变更。
- Reasoning Engine 只读取图快照并输出假设及证据缺口，不直接写图。
- Reproduction Engine 产生实验与验证证据，仍由 Runtime 校验后写入。

这样既保留 Investigation 的证据构建能力，也保证 Runtime 是唯一状态管理者。

### 3.7 Knowledge 与 Skill

Skill 应作为版本化、可审计的内容资产，而不是隐藏在 Prompt 或 Python 控制流里。建议每个 Skill 至少包含：标识、版本、适用产品/版本范围、输入要求、分析步骤、允许工具、输出 schema、证据标准、安全级别和测试样例。

Obsidian 只是一个 Knowledge Source Adapter。核心知识 Contract 不应依赖 Vault 路径、Markdown frontmatter 或 Obsidian API，以便未来替换为 Git、搜索服务或数据库。产品版本解析必须先于知识检索，避免将其他版本行为误判为异常。

### 3.8 Agent Host 可替换性

三类 Host 统一通过 `DecisionProviderPort` 与受控的 Runtime API 工作：

- Codex/CodeBuddy 客户端：加载 Skill，通过 Runtime 暴露的查询/决策接口参与选择；工具执行仍受 Runtime Policy 控制。
- Codex/CodeBuddy CLI：使用同一 Contract 的 CLI/stdio 或 HTTP Adapter。
- 自研 Agent + 小模型：由 LangChain Adapter 实现决策端口；LangChain 类型在 Adapter 内部终止。

Host 不拥有 Incident 权威状态，也不直接访问危险工具。相同 Fake 场景应可替换不同 Host 而不修改 Runtime、Engine 或 Contract。

### 3.9 API 与持久化

- FastAPI 只负责鉴权、请求/响应转换、错误映射、流式事件订阅和调用 application facade。
- API 从 `/api/v1` 起步，API schema 与内部事件 schema 分开演进。
- 第一阶段使用内存 Repository 完成 Fake E2E；随后增加持久化 Adapter，避免过早绑定数据库。
- 状态更新与事件追加需要原子性；后续若拆服务，可采用 outbox/event transport Adapter，但当前不引入消息中间件。
- 原始证据使用 Artifact Store，元数据和可查询关系使用 Repository；敏感数据采用分级、脱敏和保留策略。

## 4. 建议目录结构

```text
.
├── AGENTS.md
├── README.md
├── pyproject.toml
├── docs/
│   ├── architecture/
│   │   ├── 00-architecture-plan.md
│   │   ├── decisions/                 # ADR
│   │   └── diagrams/
│   ├── contracts/
│   ├── runbooks/
│   └── security/
├── skills/
│   ├── product/
│   └── troubleshooting/
├── src/
│   └── ai_incident_agent/
│       ├── contracts/                 # 公共 Pydantic v2 models/events
│       │   └── v1/
│       ├── ports/                     # Protocol/ABC；只引用 contracts
│       ├── domain/                    # 纯领域规则与图/状态不变量
│       ├── runtime/                   # 状态机、编排、policy、预算、恢复
│       ├── engines/
│       │   ├── knowledge/
│       │   ├── reasoning/
│       │   ├── investigation/
│       │   └── reproduction/
│       ├── adapters/
│       │   ├── inbound/
│       │   │   ├── api/               # FastAPI
│       │   │   └── cli/
│       │   └── outbound/
│       │       ├── agent_hosts/
│       │       ├── llm/               # LangChain 限定区域
│       │       ├── mcp/
│       │       ├── knowledge/
│       │       ├── observability/
│       │       ├── reproduction/
│       │       └── persistence/
│       ├── application/               # 薄用例门面，不承担领域编排
│       └── bootstrap/                 # 配置与唯一组合根
├── tests/
│   ├── architecture/                  # import 边界检查
│   ├── unit/
│   │   ├── contracts/
│   │   ├── domain/
│   │   ├── runtime/
│   │   └── engines/
│   ├── contract/                      # 每个 Port 的共享契约测试
│   ├── integration/
│   ├── e2e/
│   │   └── fake/
│   ├── fakes/                         # Fake ports、clock、IDs、fixtures
│   └── fixtures/
└── scripts/                           # 仅开发/验证脚本
```

说明：这是建议结构，不代表本步骤已创建除本文档外的任何目录或文件。`application` 只提供启动、查询、提交审批等用例入口；跨 Engine 的状态推进必须委托 Runtime，避免形成第二个编排中心。

## 5. Fake/Mock 与测试策略

从第一天建立一条确定性的完整 Fake E2E：

1. Fake Incident 描述一个已知版本回归。
2. Fake Knowledge 返回该版本的预期行为和排障 Skill。
3. Fake Decision Provider 返回固定规划与假设。
4. Fake Investigation 提供一组支持/反对证据。
5. Fake Reproduction 创建无真实副作用的实验结果。
6. Fake Verifier 证明复现信号与假设一致。
7. Runtime 走完整状态机并产出可断言的事件序列和 Evidence Graph。

测试层次：

- 单元测试：状态转换、图不变量、policy、重试、timeout、loop budget、schema 校验。
- Contract tests：所有 Fake 与真实 Adapter 必须通过同一套 Port 行为测试。
- 集成测试：FastAPI + Runtime + in-memory adapters；各外部 Adapter 使用受控测试替身。
- Fake E2E：无网络、无外部凭据、可重复执行，覆盖成功、证据不足、审批拒绝、超时和取消。
- 架构测试：检查禁止 import、LangChain/FastAPI 使用范围和 Engine 交叉依赖。
- 回归测试：每个线上问题修复都沉淀为最小 fixture/场景，避免只增加 Prompt 示例。

所有异步边界使用 `pytest-asyncio`，API 测试使用 `httpx`。质量门禁至少包含 `ruff check`、`ruff format --check`、`mypy` 和 `pytest`，并记录实际执行命令与结果。

## 6. 后续实施顺序

### Step 1：项目骨架与质量门禁

先编写失败的架构/冒烟测试，再建立 `pyproject.toml`、src layout、最小包、pytest/pytest-asyncio/httpx、ruff 和 mypy 配置；补充 README 与适用于本仓库的 `AGENTS.md`。验收标准是本地一条命令能运行全部质量检查。

### Step 2：Contracts v1 与序列化契约

测试优先定义 Incident、Workflow、Hypothesis、Evidence、Experiment、Decision、Approval 和错误模型；覆盖严格校验、JSON round-trip、版本字段与兼容性样例。此阶段不接 LLM、FastAPI 或真实工具。

### Step 3：Ports 与共享 Contract Test Kit

定义 Engine、Decision、Repository、Tool、Policy 和 Approval ports；创建可供 Fake/真实实现复用的行为测试。明确 deadline、取消、幂等和错误语义。

### Step 4：Domain 与 Core Runtime 最小闭环

测试优先实现状态机、Incident State、Evidence Graph 不变量、Schema Validator、Policy decision、retry/timeout、loop control 和 human approval。Runtime 只对 ports 编程。

### Step 5：全套 Fake Adapters 与 Fake E2E

实现 deterministic clock/ID、in-memory repositories、Fake Knowledge/Decision/Investigation/Reproduction/Verifier 和 Fake Tool Executor，跑通端到端成功与失败路径。这是进入真实集成前的架构验收门。

### Step 6：四个 Engine 的最小能力

按 Knowledge → Reasoning → Investigation → Reproduction/Verifier 的顺序分别测试和实现。每次只实现本 Engine，使用 Fake ports 隔离其他模块；禁止 Engine 间直接 import。

### Step 7：FastAPI 与 CLI Inbound Adapters

提供创建 Incident、查询状态、推进/取消运行、提交审批和读取证据的 v1 API；CLI 复用 application facade。使用 httpx 完成集成测试。

### Step 8：Knowledge/Skill 与 Obsidian Adapter

定义 Skill manifest/version 规则、产品版本匹配、来源引用和检索 Adapter；用固定 Vault fixture 验证，不让 Obsidian 格式进入核心 Contract。

### Step 9：Agent/LLM Adapters

接入 Codex/CodeBuddy host bridge 和自研 LangChain Agent Adapter。加入结构化输出、无效输出修复上限、prompt/skill 版本记录和 Fake 对照测试。

### Step 10：Investigation 真实 Adapters

按价值和安全性逐步接入 Trace、Logs、Metrics、K8s、Change History 和 Service Graph，再生成 Evidence Graph 变更提案。每个 Adapter 必须先通过共享 Contract tests，并支持只读模式和脱敏。

### Step 11：Reproduction 真实 Adapters

先接隔离环境与 API/Playwright/Shell，再接 k6、mitmproxy/Toxiproxy、Chaos Mesh。危险动作默认拒绝或要求审批，具备作用域限制、超时、清理与回滚验证。

### Step 12：持久化、恢复与并发控制

增加数据库和 Artifact Store Adapter，验证崩溃恢复、乐观并发、幂等、审计链、保留策略和 schema migration；仍保留内存实现用于测试。

### Step 13：安全、可观测性与生产化

完善凭据隔离、租户边界、RBAC、审计、数据脱敏、资源配额、指标、Trace、灾难恢复和运维手册；以真实但脱敏的历史案例开展回归与性能测试。

### Step 14：可选服务拆分

仅当容量、故障隔离或组织边界确有需要时，将 Engine/Adapter 拆为独立服务。拆分应实现既有 Ports 的远程 Adapter，不改变 Domain Contract 和 Runtime 语义。

每一步都遵循：先写失败测试 → 最小实现 → 实际执行验证 → 修复失败 → 全量回归 → 记录验证证据。未通过当前步骤验收前不进入下一步骤。

## 7. 冲突、风险与待决策项

### 当前冲突

- 用户要求先阅读根目录 `AGENTS.md`，但仓库中不存在该文件；无法执行其中可能存在的额外要求。应在 Step 1 与团队共同建立，不能擅自引用相邻仓库版本。
- Evidence Graph 同时被列为 Investigation Engine 与 Core Runtime 能力；本方案建议由 Runtime/Domain 持有权威状态，Investigation 负责生成证据与变更提案，需团队确认。
- `origin/main` 显示为 `gone` 且仓库无提交；多人并行开发前需要确认远端、默认分支和首次提交策略。

### 主要架构风险

- **Runtime 与 Reasoning 边界漂移**：若 Planner 直接控制工具和循环，Runtime 会失去唯一编排权。应让 Reasoning 只输出结构化提案。
- **Contract 过早膨胀**：一次设计覆盖所有工具会形成巨型模型。应以最小 Fake E2E 驱动 v1，并用版本化扩展。
- **公共模型与持久化模型混同**：会阻碍服务拆分和迁移。Adapter 内部应做显式映射。
- **LLM 非确定性**：无 schema、置信度和循环预算会造成失控。所有决策需验证，并提供 deterministic Fake。
- **证据可信度**：日志可能缺失、时钟漂移或被截断。Evidence 必须记录来源、时间、采集条件、哈希和完整性。
- **危险副作用**：Shell、压力和故障注入可能影响生产。需要环境分级、默认拒绝、审批、幂等、终止开关和清理验证。
- **敏感信息泄漏**：日志、Trace、Prompt 和 Agent Host 可能暴露凭据或个人信息。必须在 Adapter 边界脱敏并限制原始对象访问。
- **MCP 能力差异**：不同 Server 的 schema、错误和取消行为不一致。需由 MCP Adapter 标准化并通过 Contract tests。
- **超时与取消传播**：异步工具未正确取消会遗留资源。所有 Port 都应接收 deadline/cancellation context。
- **并发开发冲突**：多人同时修改 Contracts、Ports 和组合根风险最高。建议设置模块 owner，Contract 变更走 ADR/兼容性评审，并以小提交集成。
- **依赖版本风险**：Python、FastAPI、Pydantic、LangChain 等具体版本尚未确定。Step 1 应锁定兼容版本并用 CI 验证；LangChain 只能作为可替换 Adapter 依赖。
- **过早微服务化**：会把 Contract 尚未稳定的问题放大为分布式复杂度。首版保持模块化单体。

### 实施前需团队确认

- 包名、公开 API 命名和 Contract 版本策略。
- Incident/Evidence 的数据库与对象存储选型（不阻塞内存版）。
- 首批支持的产品、版本、Obsidian Vault 结构及数据分级。
- 首批真实观测数据源和复现环境边界。
- 哪些动作必须人工审批，以及生产环境是否完全禁止故障注入。
- Codex/CodeBuddy Host 与 Runtime 的首选传输方式和鉴权方式。

## 8. 本步骤明确未实施的内容

本步骤没有：

- 创建 Python 包、`pyproject.toml`、README、`AGENTS.md` 或 CI 配置。
- 安装或引入 FastAPI、LangChain、Pydantic、pytest 等依赖。
- 编写任何 Engine、Runtime、Contract、Port、API、Adapter、Skill 或业务实现代码。
- 编写或执行业务测试、Fake E2E、lint、类型检查或服务启动。
- 删除、迁移或大规模修改任何既有内容。
- 连接 LLM、MCP、Obsidian、K8s、日志、指标、浏览器、Shell 或故障注入系统。
- 自动进入 Step 1 或进行任何外部系统变更。

