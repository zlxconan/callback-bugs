# 连延斌 — Core Runtime / Contracts / Generic Skill Runtime 守护任务书

> 开发前先阅读根目录 `AGENTS.md` 与本文件。技术栈统一：Python 3.11+ / FastAPI / Pydantic v2。Core Runtime 不得依赖 LangChain。

## 1. 模块定位

负责整个系统的**确定性骨架和公共协议守护**。

核心原则：**Runtime 不负责聪明，Runtime 负责稳定。**

职责：Incident State、Workflow/State Machine、RuntimeTask、Engine 调度、Retry/Timeout、Loop Control、Human Approval、Policy、Validator、Audit、Repository、Contract/Port 守护，以及 Generic Skill Runtime 的 Registry、Loader、Manifest、Resolver、Plugin Validation 和内存生命周期。

Runtime 不得接入 LLM。

Generic Skill Runtime 只管理插件元数据和生命周期，不负责真实 Product Skill 内容、Tool Skill、产品事实解析或 Incident 状态推进。Core Runtime 本身不得直接读取 Product Plugin。

## 2. 代码边界

```text
src/ops_agent/contracts/
src/ops_agent/core/
src/ops_agent/bootstrap/
src/ops_agent/skill_runtime/
tests/contracts/
tests/core/
tests/e2e/
docs/interfaces/
docs/architecture/
```

你是公共接口主要维护者，但重大接口修改仍需团队评审。

## 3. 核心职责

### Contract 守护

重点保持稳定：ProblemContext、ProductContext、KnowledgeContext、HypothesisSet、EvidencePlan、Evidence、ExperimentPlan、ExperimentResult、VerificationResult、ReflectionResult、RootCauseAssessment、IncidentState、RuntimeTask、TaskResult、RCAReport。

### Port 守护

确保 KnowledgePort、ReasoningPort、InvestigationPort、ReproductionPort、RuntimePort、StateRepositoryPort 的 Fake/Real 实现兼容。

### Runtime

显式状态机至少覆盖仓库当前定义的：CREATED、NORMALIZE、KNOWLEDGE_LOOKUP、HYPOTHESIS、EVIDENCE_PLAN、INVESTIGATE、ROOT_CAUSE_ASSESSMENT、EXPERIMENT_PLAN、REPRODUCE、VERIFY、REFLECT、RCA、PERSIST、WAITING_HUMAN、COMPLETED、FAILED。

### Generic Skill Runtime

维护 `BUILTIN_METHOD`、`PRODUCT`、`TROUBLESHOOTING` 类型，提供安全入口校验、兼容性、发现、安装索引、卸载和产品/版本精确路由。Tool Skill 不进入该 Incident Registry。

## 4. 对接关系

| 模块 | 你提供 | 对方提供 |
|---|---|---|
| Knowledge | KnowledgePort 调用上下文 | KnowledgeContext |
| Reasoning | RuntimeTask/ReasoningContext | Hypothesis/EvidencePlan/Reflection |
| Investigation | EvidenceRequest | Evidence |
| Reproduction | ExperimentPlan + Policy | ExperimentResult |
| Integration | RuntimePort / Runtime MCP | Agent Host TaskResult |

你是编排者，但不能侵入各 Engine 内部实现。

## 5. 第一阶段 MVP

第一目标不是增加业务功能，而是保证：

```text
FakeKnowledge + FakeReasoning + FakeInvestigation + FakeReproduction
```

从 ProblemContext 到 RCAReport 的完整闭环始终稳定，并支持每个 Real Engine 逐个替换 Fake 而 Runtime 不改。

## 6. Interface Change 流程

任何人提出接口修改，你需要检查：是否真有必要、是否破坏字段、是否影响 Fake、是否影响历史 JSON、是否要升级 schema_version、是否更新 Contract Test、docs/interfaces 和受影响 E2E。

禁止为了单一模块方便污染公共 Contract。

## 7. 测试要求

持续维护：

```text
tests/contracts/
tests/core/
tests/e2e/test_fake_incident_flow.py
tests/e2e/test_engine_replacement.py
```

覆盖：合法/非法状态流转、Retry、Timeout、Loop 超限、Evidence 不足、Reflection、Experiment 失败、Human Approval、Engine unavailable、Completed 不可重复执行、Audit Event、State 恢复。

## 8. 独立验收

```bash
pytest tests/contracts -q
pytest tests/core -q
pytest tests/e2e/test_fake_incident_flow.py -q
ruff check .
mypy src
```

还需静态检查：Core 不 import LangChain、Contracts 不 import LangChain、Core 不依赖具体 Engine 实现、Engine 替换不改 Runtime、所有错误有标准 ErrorResponse。

## 9. 交付物

Contract v1/Port v1 守护、Runtime、Generic Skill Runtime、Plugin Spec/Validation、State Repository、Validator、Policy、Audit、Fake E2E、接口/架构文档和验证记录。

最终验收：**任何一个 Engine 从 Fake 替换为 Real 时，Core Runtime 无需修改；完整流程仍可闭环。**
