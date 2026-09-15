# Canonical Skill、MCP、Runtime 与 Agent 边界

> 状态：Implemented  
> 日期：2026-09-15  
> 范围：Step 8 Canonical Skill v1 与 Builder 抽象

## 1. 核心分工

```text
Canonical Skill：定义应该如何分析、选择证据和规划实验
Agent：          根据当前 Contract 快照完成本轮推理与选择
Runtime：        管理 Stage、状态、循环、重试、超时、审批和终止
MCP：            校验 Contract 并执行被允许的工具能力
```

完整控制关系：

```text
RuntimeTask
   |
   v
Agent --loads--> Canonical Skill
   |                  |
   | structured       | method and allowed MCP names
   v                  v
TaskResult        MCP Registry -> Port -> Adapter
   |
   v
Core Runtime -> validates and chooses next Stage
```

Skill 不保存 IncidentState，不生成或修改 RuntimeTask，不控制 Reflection 循环，也不因为列出了一个 MCP Tool 就获得调用权限。MCP 不包含 Planner、Hypothesis、Reflection 或 State Machine。Agent 的自然语言输出只有转换成既有 Contract 并被 Runtime 接受后才影响状态。

## 2. Canonical Source

唯一业务 Skill 源位于仓库根目录 `skills/<skill-name>/`：

```text
skills/<skill-name>/
├── skill.toml   # 机器元数据和引用
└── SKILL.md     # 唯一方法论正文
```

`skill.toml` 包含：

- `name`：小写 kebab-case 唯一名称；
- `version`：语义版本；
- `description`：发现和路由描述；
- `input_contracts` / `output_contracts`：`ops_agent.contracts` 中的模型名；
- `mcp_tools`：Step 7 Registry 中已存在的 Tool 名。

`SKILL.md` 使用兼容 Codex 的 name/description frontmatter，并固定包含目标、场景、输入、输出、操作步骤、允许 MCP、禁止行为、退出条件、失败处理和示例。机器元数据与正文职责不同，不维护两份操作逻辑。

## 3. v1 Skill 目录

| Skill | 主要输入 | 主要输出 | 方法论重点 |
|---|---|---|---|
| `incident-analysis` | `StartIncidentRequest`, `RuntimeTask` | `TaskResult`, `RCAReport` | 领取和提交任务，但不拥有状态机 |
| `product-knowledge` | `ProblemContext`, `KnowledgeQuery` | `ProductContext`, `KnowledgeContext` | 产品 → 版本 → 功能 → 组件 → 依赖 |
| `troubleshooting` | `KnowledgeQuery` | `TroubleshootingContext` | 产品 → 版本 → 故障 → 现象 → 原因 → 操作 → 验证 |
| `hypothesis-generation` | `HypothesisGenerationRequest` | `HypothesisSet` | 分离事实、推断、假设和证据缺口 |
| `evidence-planning` | `EvidencePlanningRequest`, `Hypothesis` | `EvidencePlan`, `EvidenceRequest` | Hypothesis → Missing Evidence → EvidenceRequest |
| `reflection` | `ReflectionRequest` | `ReflectionResult` | 有界复盘并建议 next_action，不自行循环 |
| `reproduction-planning` | `ExperimentPlanningRequest`, `Hypothesis` | `ExperimentPlan` | Hypothesis → ExperimentPlan |
| `rca-report` | `RootCauseAssessment`, `VerificationResult`, `IncidentState` | `RCAReport`, `TaskResult` | 严格分离事实、推断、根因、建议和未验证项 |

## 4. 引用与权限验证

`SkillCatalog` 使用 Python 3.11 `tomllib` 加载元数据，避免引入额外 YAML 运行依赖。`validate` 执行：

1. Skill 名唯一且与目录一致；
2. 元数据满足 Pydantic Schema；
3. 每个输入/输出名称都解析到现有 Pydantic Contract；
4. 每个 MCP 名都存在于 runtime、knowledge、observability、code 或 reproduction Registry；
5. `SKILL.md` 必须存在。

允许 MCP 列表是能力上限声明，不是授权。真实调用仍受 MCP Tool 的 risk/write 元数据、Runtime Policy、Human Approval 和部署身份控制。Skill 不得通过列出高风险 Tool 绕过审批。

## 5. Builder 抽象

`SkillBuilder` Protocol 固定构建入口：

```python
build(skill, *, target, destination) -> BuiltSkillArtifact
```

`SkillTarget` 已预留：

- `codex`
- `codebuddy`
- `local`

这对应未来命令语义：

```text
skill build --target codex
skill build --target codebuddy
skill build --target local
```

当前 `CanonicalSkillBuilder` 对三个目标输出同一份 `SKILL.md` 正文和带 target 的 manifest。它只在目标目录创建构建产物，不反向修改 Canonical Source。未来平台 Adapter 只能转换包装、发现元数据或工具声明，不能复制或重写业务步骤；公共 Contract 和 MCP Tool 名保持不变。

## 6. 版本与变更规则

- 修改措辞但不改变输入输出或决策语义：patch version。
- 增加兼容步骤、Contract 或 MCP 能力：minor version。
- 删除/重命名 Contract、改变证据标准或退出语义：major version，并与 Contract/MCP 版本一起迁移。
- 三个目标始终从同一个版本的 Canonical Source 构建，禁止在目标产物中手工修补业务逻辑。

## 7. 测试

- `tests/skills/test_catalog.py`：八个 Skill、元数据、固定章节、Contract 引用和 MCP Tool 引用。
- `tests/skills/test_builder.py`：Codex、CodeBuddy、Local 三目标 smoke test，确认正文保持 Canonical。
- `tests/skills/conftest.py`：从真实 Step 7 Registry 汇总工具名；测试不会用手写白名单掩盖不存在的工具。
- Skill 入口另使用 Codex `quick_validate.py` 校验 frontmatter 与命名。

## 8. Done 标准与限制

Step 8 Done：八个 Skill 全部存在且含十项必需内容；特殊方法链明确；Contract 与 MCP 引用无悬空；三目标 Builder 可构建；Skill 不实现 Runtime/MCP 职责；全量 pytest、ruff、格式和 mypy 通过。

当前限制：

- 尚无 `skill` 命令行程序；Builder API 已预留命令所需 target 和输出语义。
- 未实现 Codex、CodeBuddy 或 Local 的平台专属包装，因为目前没有需要分叉的已确认差异。
- Skill 内容是第一版方法论，尚未经过真实生产 Incident 评估；后续应以真实失败案例做独立行为测试，而不是复制平台版本。
