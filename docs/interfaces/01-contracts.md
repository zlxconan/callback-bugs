# Core Contracts v1

> 状态：**Frozen**  
> Schema version：`1.0`  
> Python package：`ops_agent.contracts`  
> 冻结日期：2026-09-15

本文定义模块化单体中 Runtime、四个 Engine、Agent Host 与 Adapter 之间的第一版公共语言。这里的 Frozen 表示 v1 的字段名、字段语义、类型、必填性、ID 格式和枚举现有值不得发生不兼容修改；新增版本应使用新的 `schema_version` 和迁移策略。

## 1. 通用信封

20 个核心 Contract 均继承 `ContractBase`，因此直接携带以下字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `schema_version` | literal `"1.0"` | 否，默认 `1.0` | Contract schema 版本；v1 只接受 `1.0`。 |
| `incident_id` | string | 是 | 关联 Incident，格式 `INC-xxx`。 |
| `request_id` | string | 是 | 请求、关联或 Evidence Request 标识，格式 `REQ-xxx`。 |
| `timestamp` | timezone-aware datetime | 是 | Contract 产生时间，JSON 使用 RFC 3339。 |
| `source` | non-empty string | 是 | 产生该对象的模块、Adapter、Agent 或操作者。 |
| `metadata` | JSON object | 否，默认 `{}` | 非核心扩展信息；不得用来改变已冻结字段语义。 |

所有模型均使用 Pydantic v2，`extra="forbid"`，支持 `model_validate`、`model_dump`、`model_dump_json`、`model_validate_json` 与 `model_json_schema`。嵌套公共值同样拒绝未声明字段。

### ID 规则

| 对象 | 格式 |
|---|---|
| Incident | `INC-[A-Za-z0-9][A-Za-z0-9._-]*` |
| Request | `REQ-[A-Za-z0-9][A-Za-z0-9._-]*` |
| Hypothesis | `H-[A-Za-z0-9][A-Za-z0-9._-]*` |
| Evidence | `E-[A-Za-z0-9][A-Za-z0-9._-]*` |
| Experiment | `EXP-[A-Za-z0-9][A-Za-z0-9._-]*` |
| Runtime Task | `TASK-[A-Za-z0-9][A-Za-z0-9._-]*` |
| Audit Event | `AUD-[A-Za-z0-9][A-Za-z0-9._-]*` |
| RCA Report | `RCA-[A-Za-z0-9][A-Za-z0-9._-]*` |

## 2. Context Contracts

### 2.1 ProblemContext

- **用途**：规范化问题症状、影响面与首次观测环境。
- **字段**：`title` 标题；`description` 描述；`symptoms` 非空症状列表；`severity` 严重度；`observed_at` 观测时间；`affected_services` 受影响服务；`environment` 结构化环境信息。
- **产生者**：Incident API、CLI、Agent Host 或人工录入 Adapter。
- **消费者**：Runtime、Knowledge、Reasoning、Investigation、Reproduction。
- **JSON 示例**：[problem-context.json](../../examples/contracts/problem-context.json)

### 2.2 ProductContext

- **用途**：确定具体产品、版本、组件和应该出现的行为。
- **字段**：`product_name` 产品；`product_version` 版本；`component` 组件；`deployment_environment` 部署环境；`expected_behavior` 预期行为；`configuration` 相关配置快照。
- **产生者**：Knowledge Engine、产品目录或版本解析 Adapter。
- **消费者**：Runtime 及四个 Engine。
- **JSON 示例**：[product-context.json](../../examples/contracts/product-context.json)

### 2.3 KnowledgeContext

- **用途**：携带带来源的版本知识与适用 Skill。
- **字段**：`query` 原始知识问题；`facts` 已检索事实；`references` 原始资料引用；`skill_ids` 适用 Skill；`limitations` 知识覆盖限制。
- **产生者**：Knowledge Engine/Knowledge Source Adapter。
- **消费者**：Runtime、Reasoning Engine、Agent Host。
- **JSON 示例**：[knowledge-context.json](../../examples/contracts/knowledge-context.json)

### 2.4 TroubleshootingContext

- **用途**：避免重复已完成的排障动作，并传递安全和现场约束。
- **字段**：`actions_taken` 已执行动作；`observed_results` 对应结果；`known_workarounds` 已知缓解方案；`constraints` 禁止项或运行限制。
- **产生者**：Incident API、人工操作者、Knowledge Engine。
- **消费者**：Runtime、Reasoning、Investigation、Reproduction。
- **JSON 示例**：[troubleshooting-context.json](../../examples/contracts/troubleshooting-context.json)

## 3. Hypothesis Contracts

### 3.1 Hypothesis

- **用途**：表达一个可证伪的原因候选，并严格分开事实、推断和假设前提。
- **字段**：`hypothesis_id` 为 `H-xxx`；`fact` 是已知事实；`inference` 是从事实得出的解释；`assumption` 是尚未验证的前提；`confidence` 范围 `[0,1]`；`supporting_evidence` 和 `contradicting_evidence` 引用 `E-xxx`；`missing_evidence` 引用 `REQ-xxx`；`status` 表示生命周期。
- **产生者**：Reasoning Engine 或受控 Agent Adapter。
- **消费者**：Runtime、Investigation、Reproduction、Verifier、RCA renderer。
- **JSON 示例**：[hypothesis.json](../../examples/contracts/hypothesis.json)

状态枚举：`proposed`、`testing`、`supported`、`contradicted`、`confirmed`、`rejected`、`inconclusive`。

### 3.2 HypothesisSet

- **用途**：传递一组候选及其明确优先级。
- **字段**：`hypotheses` 非空 Hypothesis 列表；`prioritized_hypothesis_ids` 是无重复的优先顺序且只能引用集合成员；`selection_rationale` 说明排序理由。
- **产生者**：Reasoning Engine。
- **消费者**：Runtime、Investigation、Reproduction、Reflection。
- **JSON 示例**：[hypothesis-set.json](../../examples/contracts/hypothesis-set.json)

## 4. Evidence Contracts

### 4.1 EvidenceRequest

- **用途**：描述为验证或反驳 Hypothesis 所需的一次有界采集请求。
- **字段**：通用 `request_id` 同时是该请求 ID；`hypothesis_ids` 关联 `H-xxx`；`evidence_type` 类型；`description` 目的；`query` 查询；`acquisition_method` 工具能力；`priority` 范围 1～5；`required` 是否为完成门槛；`time_range` 可选采集时间窗。
- **产生者**：Reasoning Engine、Reflection。
- **消费者**：Runtime、Investigation Engine、Tool Adapter。
- **JSON 示例**：[evidence-request.json](../../examples/contracts/evidence-request.json)

### 4.2 EvidencePlan

- **用途**：把 Evidence Request 组织为可执行的采集计划。
- **字段**：`objective` 计划目标；`requests` 非空请求列表；`completion_criteria` 非空完成条件。
- **产生者**：Reasoning Engine。
- **消费者**：Runtime、Investigation Engine。
- **JSON 示例**：[evidence-plan.json](../../examples/contracts/evidence-plan.json)

### 4.3 Evidence

- **用途**：保存带来源、可追溯、可关联假设的现场或实验观察。
- **字段**：`evidence_id` 为 `E-xxx`；`evidence_type` 来源数据类型；`raw_reference` 包含 URI、可选 digest/media type；`structured_value` 是解析后的 JSON 值；`observed_at` 是证据自身时间；`supports_hypotheses` 和 `contradicts_hypotheses` 引用 `H-xxx`；`confidence` 范围 `[0,1]`；`acquisition_status` 表示获取状态。
- **产生者**：Investigation/Reproduction Adapter，经对应 Engine 标准化并由 Runtime 接纳。
- **消费者**：Runtime、Reasoning、Verifier、RCA renderer。
- **JSON 示例**：[evidence.json](../../examples/contracts/evidence.json)

同一 Evidence 不允许同时支持和反驳同一个 Hypothesis。类型枚举为 `log`、`metric`、`trace`、`event`、`configuration`、`code`、`change`、`user_report`、`experiment`、`other`；获取状态为 `requested`、`collecting`、`acquired`、`unavailable`、`failed`。

## 5. Experiment and Verification Contracts

### 5.1 ExperimentPlan

- **用途**：定义可审计、可回滚的复现实验。
- **字段**：`experiment_id` 为 `EXP-xxx`；`title`、`objective`；`hypothesis_ids`；`environment` 结构化环境要求；`steps` 是有序的 `step_number/action/expected_outcome`；`success_criteria`；`rollback_steps`；`risk_level`；`requires_approval`。
- **产生者**：Reproduction Engine。
- **消费者**：Runtime、Policy、Human Approval、Reproduction Adapter。
- **JSON 示例**：[experiment-plan.json](../../examples/contracts/experiment-plan.json)

### 5.2 ExperimentResult

- **用途**：记录一次实验的状态、观察和产出证据。
- **字段**：`experiment_id` 关联计划；`status`；`started_at`、`completed_at`；`observations`；`evidence_ids`；`outputs` 结构化结果。完成时间不得早于开始时间。
- **产生者**：Reproduction Engine/Adapter。
- **消费者**：Runtime、Verifier、Reasoning、RCA renderer。
- **JSON 示例**：[experiment-result.json](../../examples/contracts/experiment-result.json)

### 5.3 VerificationResult

- **用途**：判断实验和证据是否确认或否定目标 Hypothesis。
- **字段**：`status` 为 `confirmed/rejected/inconclusive`；`hypothesis_ids`；`experiment_ids`；`evidence_ids`；`confirmed_claims`、`rejected_claims`、`unverified_claims`；`rationale`；`confidence`。
- **产生者**：Verifier/Reproduction Engine。
- **消费者**：Runtime、Reasoning、RootCauseAssessment、RCA renderer。
- **JSON 示例**：[verification-result.json](../../examples/contracts/verification-result.json)

## 6. Reflection and Assessment Contracts

### 6.1 ReflectionResult

- **用途**：给 Runtime 一个有界的下一步建议，不直接执行或推进状态。
- **字段**：`summary`；`retained_hypothesis_ids`、`rejected_hypothesis_ids`；`new_hypotheses`；`missing_evidence`；`next_action`；`should_continue`。
- **产生者**：Reasoning Engine/Reflection component。
- **消费者**：仅由 Runtime 决策使用，其他 Engine 可读取 Runtime 选定后的输入。
- **JSON 示例**：[reflection-result.json](../../examples/contracts/reflection-result.json)

`next_action` 枚举：`collect_evidence`、`revise_hypotheses`、`plan_experiment`、`assess_root_cause`、`request_human_input`、`stop`。

### 6.2 RootCauseAssessment

- **用途**：在最终报告前形成证据支撑的根因判断。
- **字段**：`status` 为 `confirmed/probable/possible/unknown`；`confirmed_facts`；`inferences`；`root_causes`；`unverified_items`；`overall_confidence`。事实、推断和根因分别存储。
- **产生者**：Reasoning Engine，在 Runtime 校验后接纳。
- **消费者**：Runtime、RCA renderer、API。
- **JSON 示例**：[root-cause-assessment.json](../../examples/contracts/root-cause-assessment.json)

## 7. Runtime Contracts

### 7.1 IncidentState

- **用途**：Runtime 持有的可序列化权威 Incident 快照。
- **字段**：`status` 工作流阶段；`revision` 乐观并发版本；`problem` 必填；`product`、`knowledge`、`troubleshooting`、`hypotheses` 可选；`evidence`、`experiment_plans`、`experiment_results`、`verification_results`；`root_cause_assessment`。
- **产生者**：Core Runtime。
- **消费者**：Core Runtime repository、API、Agent Host；Engine 只获得所需快照。
- **JSON 示例**：[incident-state.json](../../examples/contracts/incident-state.json)

状态枚举覆盖 `received` 到 `resolved/inconclusive/failed/cancelled` 的显式工作流阶段。

### 7.2 RuntimeTask

- **用途**：Runtime 发给一个 Port 的单个、可重试工作单元。
- **字段**：`task_id` 为 `TASK-xxx`；`kind` 目标能力；`status`；`payload` JSON 输入；`depends_on` 依赖任务；`attempt`、`max_attempts`；`deadline`。
- **产生者**：Core Runtime。
- **消费者**：Engine Port、Tool/Agent Adapter、task repository。
- **JSON 示例**：[runtime-task.json](../../examples/contracts/runtime-task.json)

### 7.3 TaskResult

- **用途**：Port 对 RuntimeTask 返回的终态结果。
- **字段**：`task_id`；终态 `status`；`output`；`evidence_ids`；可选 `error`；`started_at`、`completed_at`。失败必须带 ErrorResponse，结束时间不得早于开始时间。
- **产生者**：Engine/Adapter Port 实现。
- **消费者**：Core Runtime、audit sink、task repository。
- **JSON 示例**：[task-result.json](../../examples/contracts/task-result.json)

## 8. Output and Governance Contracts

### 8.1 RCAReport

- **用途**：对外提供最终根因分析报告，防止把推断包装成事实。
- **字段**：`report_id` 为 `RCA-xxx`；`title`；`executive_summary`；`confirmed_facts` 是带 `E-xxx` 的事实；`inferences` 独立保存推断；`root_causes` 包含置信度及 `H-xxx/E-xxx`；`minimal_reproduction_conditions` 保存最小复现条件；`remediation_recommendations` 包含 action/rationale/priority；`unverified_items`；`evidence_chain` 用显式关系连接证据与目标。
- **产生者**：RCA renderer，经 Runtime 从已验证状态构建。
- **消费者**：API、Agent Host、操作者、审计和知识沉淀流程。
- **JSON 示例**：[rca-report.json](../../examples/contracts/rca-report.json)

RCAReport 的五类内容禁止合并或复用为同一自由文本字段：已确认事实、推断、根因、修复建议、未验证事项。`evidence_chain` 是单独的结构化证据链。

### 8.2 ErrorResponse

- **用途**：统一模块、Port 和 HTTP 边界的机器可读错误。
- **字段**：`code` 稳定错误码；`message` 人类可读消息；`category` 错误分类；`retryable`；`details` JSON 详情。
- **产生者**：Schema Validator、Policy、Runtime、Engine 或 Adapter。
- **消费者**：Runtime、API、Agent Host、audit sink。
- **JSON 示例**：[error-response.json](../../examples/contracts/error-response.json)

分类枚举：`validation`、`policy`、`transient`、`timeout`、`dependency`、`user_action_required`、`terminal`。

### 8.3 AuditEvent

- **用途**：形成可关联的运行审计链。
- **字段**：`audit_event_id` 为 `AUD-xxx`；`event_type`；`actor`；`action`；`outcome`；`target_ref`；`details`；可选 `previous_event_id`。
- **产生者**：Runtime 及受控边界 Adapter。
- **消费者**：Audit sink、合规查询、运行诊断。
- **JSON 示例**：[audit-event.json](../../examples/contracts/audit-event.json)

## 9. 冻结和演进规则

### 允许的兼容扩展

- 在 `metadata`、`environment`、`configuration`、`structured_value`、`payload`、`output`、`outputs`、`details` 中增加业务自描述 JSON 数据。
- 增加新的可选字段，但必须先更新 JSON Schema、文档、示例和兼容性测试；消费者仍须能忽略该字段或同步升级，因为 v1 当前使用 `extra="forbid"`。
- 向枚举增加值只能在确认所有消费者实现未知值降级策略后进行；否则视为版本升级。
- 增加新的 Contract 类型，不改变已有类型语义。

### 禁止在 v1 随意修改

- 删除或重命名字段、改变字段含义、类型、必填性或默认值。
- 改变 ID 前缀、正则格式或引用目标含义。
- 放宽/收紧 `confidence` 的 `[0,1]` 范围而不升级版本。
- 合并 `fact/inference/assumption`，或合并 RCAReport 的事实、推断、根因、修复建议、未验证事项与证据链。
- 改变 `timestamp/observed_at/started_at/completed_at` 的时区要求。
- 让 LangChain、FastAPI、MCP SDK、数据库或供应商对象成为公共字段类型。
- 在 v1 接受 `schema_version` 不是 `1.0` 的对象。

### 破坏性变更流程

破坏性变更必须新增 schema major/minor 策略、提供双读或迁移 Adapter、保留 v1 Contract tests 和 JSON fixtures，并记录 ADR。不得直接覆盖本文件或用 `metadata` 偷渡新语义。

## 10. 验证入口

```bash
.venv/bin/python -m pytest tests/contracts
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python -m pytest
```

`tests/contracts/test_contract_examples.py` 会逐一读取 20 个 JSON 文件，以对应模型执行 `model_validate_json`，再通过 `model_dump(mode="json")` 和 `model_validate` 完成 round trip。
