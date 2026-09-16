# Skill / Plugin / MCP / Runtime Boundary v0.2

## 1. 四个概念

- Skill：分析方法或版本化知识内容，不执行基础设施能力，不持有 IncidentState。
- Plugin：可安装、升级、卸载的 Product/Troubleshooting Skill Package。
- MCP：工具执行协议边界，不定义业务方法论。
- Runtime：唯一流程、状态、权限和停止条件所有者。

```text
Agent chooses -> Skill tells how -> Runtime permits/orders -> MCP executes
Knowledge Engine -> Skill Runtime -> Product Plugin -> KnowledgeContext
```

## 2. Built-in Method Skills

Canonical Source 只有一套，位于 `skills/builtin/`：

| Skill | 输入/输出重点 | 边界 |
|---|---|---|
| incident-analysis | RuntimeTask -> TaskResult | 驱动 next/submit，不拥有状态机 |
| hypothesis-generation | KnowledgeContext -> HypothesisSet | 不读取 Product Plugin 文件 |
| evidence-planning | Hypothesis -> EvidencePlan | 不直接采集 |
| reflection | 状态快照 -> ReflectionResult | 不自行循环 |
| reproduction-planning | Hypothesis -> ExperimentPlan | 不执行工具 |
| rca-report | 已验证状态 -> RCAReport | 不补造证据 |

`CanonicalSkillBuilder` 可为 Codex、CodeBuddy、Local 三种 Host 包装同一来源，不允许形成三套方法论。

## 3. Product Plugin Skills

Generic Skill Manifest 至少包含：`schema_version`、`name`、`skill_type`、`version`、`entrypoint`、`core_api`、`product`、`product_versions`。

支持类型：

- `BUILTIN_METHOD`
- `PRODUCT`
- `TROUBLESHOOTING`

`ops_agent.skill_runtime` 的职责：

- Loader：递归发现并加载 package；
- Validator：入口路径、兼容版本、类型范围和重复注册校验；
- Registry：安装/发现/卸载的进程内索引；
- Resolver：按 product/version/type 精确路由；
- Manifest：稳定插件元数据。

未安装或版本不匹配必须抛出明确 `SkillNotInstalledError`，禁止回退到模型记忆或其他版本。

## 4. Tool Skills 外部边界

`product-doc-crawler`、`fault-manual-parser`、`pdf-to-product-skill`、`website-to-product-skill` 不进入 Incident Runtime Registry。本仓库不实现这些 Tool Skill。

```text
Website -> Tool Skill -> Playwright MCP -> Package Builder
        -> Product Skill Repository -> install -> Skill Runtime
```

## 5. MCP 边界

- Runtime MCP：Incident 生命周期工具，属于 Core。
- Observability MCP：环境插件，供 Investigation Tool Port 使用。
- Reproduction MCP：工具/环境插件，供 Reproduction Tool Port 使用。
- Code MCP：代码 Evidence 获取。
- Knowledge MCP Adapter：可选的 KnowledgePort 远程传输，不是 Product Skill MCP。

MCP 禁止实现 Planner、Hypothesis、Evidence Planning、Reflection、RCA 方法论或 Runtime 状态转换。

Runtime MCP 当前由同一 FastAPI 进程以 Streamable HTTP 暴露在 `/mcp/runtime/`；transport 只把官方
MCP 请求映射到既有 `McpToolRegistry`，不承担 Engine 调度或 Reasoning 职责。

## 6. Agent Host

External/Local Agent 读取当前 RuntimeTask，加载对应 Built-in Method Skill，并通过 Runtime MCP 提交结构化结果。Knowledge Lookup 的产品插件解析属于 Knowledge Engine，不把插件原文件交给 Reasoning Owner。

同一 Built-in Skill、同一安装的 Product Plugin 和同一 Runtime MCP 应可被 CodeBuddy Client/CLI、Codex Client/CLI 和 Local Agent 复用。

## 7. 安全与测试

- Product Plugin entrypoint 必须位于 package 内；
- 真实 Product Skill 不得进入 Core 仓库；
- 测试插件只放 `tests/fixtures/product-skills/`；
- Tool Skill 不进入 Incident Registry；
- MCP risk/write 只是能力描述，授权仍由 Runtime Policy/Human Approval；
- 版本隔离、缺失插件、重复注册和兼容性必须测试。
