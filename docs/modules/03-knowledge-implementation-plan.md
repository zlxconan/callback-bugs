# Knowledge Engine 当前状态审计与实施方案

> 状态：已确认，第一阶段 MVP 已按本方案实现
> 基线：Architecture Baseline v0.2
> 审计日期：2026-09-16
> 范围：Knowledge Engine 最小真实插件消费闭环

## 0. 结论

Knowledge Engine 不是从零开始。仓库已经具备冻结的 Knowledge Contracts、`KnowledgePort`、模块 Service/API/Fake、最小 `PluginKnowledgeEngine`、Generic Skill Runtime、合成 Product Skill Fixture 和架构守护测试。

下一阶段应强化现有插件实现，而不是再造 Contract、Port、Registry、Loader 或 Resolver。首个验收目标是：使用 `tests/fixtures/product-skills/` 中的 TestProduct 插件，让 Real Knowledge 实现替换 `FakeKnowledgeEngine`，其余三个 Engine 保持 Fake，并由原 Core Runtime 完成 E2E。

真实 V7R2 Product Skill、Playwright Crawler Skill、官网实时采集和产品知识生产均不进入本阶段。

## 1. 当前已经有什么代码

### Knowledge 模块

- `knowledge.adapters.fake.FakeKnowledgeEngine`：确定性 `KnowledgePort` Fake。
- `knowledge.adapters.plugin.PluginKnowledgeEngine`：通过 `SkillResolver` 加载 PRODUCT/TROUBLESHOOTING 插件，并转换为公共 Context。
- `knowledge.service.KnowledgeService`：模块入口，负责 enabled 检查、Adapter 委托和统一模块错误包装。
- `knowledge.api.create_router`：只用于外部调试的 FastAPI Router。
- `KnowledgeConfig`、模块错误、HTTP 错误映射和 `ModuleHealth`。
- `knowledge.ports`：只重导出 canonical `ops_agent.ports.KnowledgePort`，没有重复定义 Protocol。

### 公共边界

- `ProblemContext`、`ProductContext`、`KnowledgeContext`、`TroubleshootingContext`、`KnowledgeQuery` 均已冻结为 Pydantic v2 Contract。
- `KnowledgeLookupResult` 已定义 Runtime 知识阶段的原子输出。
- `KnowledgePort` 已定义三个 async 方法，不能重复定义或修改签名。

### Generic Skill Runtime

- `SkillManifest` / `SkillType`；
- `SkillLoader` / `LoadedSkill`；
- `SkillValidator`；
- `SkillRegistry` / `SkillNotInstalledError`；
- `SkillResolver`；
- PRODUCT、TROUBLESHOOTING 和 BUILTIN_METHOD 类型隔离。

### 测试资产

- TestProduct 1.0：PRODUCT + TROUBLESHOOTING fixture；
- TestProduct 2.0：PRODUCT fixture；
- Registry、发现、安装/卸载、版本隔离、KnowledgePort 查询烟测；
- Knowledge Service/API Fake 测试；
- 完整 Fake E2E；
- Core/Knowledge 不依赖 crawler、Playwright、LangChain 的守护测试。

## 2. 当前实现程度

当前处于“架构烟测可用，真实实现尚未完成”的阶段。

已经证明：

1. 文件系统可以发现合成插件；
2. Manifest 可以校验 Core API、入口路径和基本产品范围；
3. Resolver 可以按精确产品、版本和 Skill 类型选择插件；
4. `PluginKnowledgeEngine` 结构上满足 `KnowledgePort`；
5. PRODUCT 插件可以产生 `ProductContext` / `KnowledgeContext`；
6. TROUBLESHOOTING 插件可以产生 `TroubleshootingContext`；
7. 入口 URI 和 SHA-256 digest 可以写入来源信息。

尚未证明：

- 插件内容本身在注册/加载时经过专用 Product/Troubleshooting Schema 校验；
- Manifest 的产品/版本与入口内容一致；
- 未知产品和未知版本有稳定、可区分的领域错误；
- 重叠版本声明不会导致选择歧义；
- PRODUCT 与 TROUBLESHOOTING 对同一产品版本形成完整可用组合；
- Real Knowledge 替换 Fake 后完成 Runtime E2E。

## 3. FakeKnowledgeEngine 当前行为

`FakeKnowledgeEngine` 完全确定性、无外部 I/O：

- `resolve_product()` 固定返回 `Order Service / 2026.09-retry-enabled`；
- `query_product_knowledge()` 固定返回“客户端重试”和“创建接口非幂等”两项事实；
- `query_troubleshooting()` 固定返回关闭自动重试的 workaround 和 Fake 环境限制；
- 所有结果继承请求 correlation 字段，`source=fake-knowledge`，并带 `metadata.fake=true`；
- 不读取 Skill Registry，也不代表真实产品行为。

它应继续保留，用于既有确定性单元测试和 Fake E2E；Real Knowledge 的验收应新增独立 E2E，不能把原 Fake E2E 改造成插件测试。

## 4. KnowledgePort 当前接口

Canonical 定义位于 `src/ops_agent/ports/engines.py`：

```python
async def resolve_product(problem: ProblemContext) -> ProductContext
async def query_product_knowledge(query: KnowledgeQuery) -> KnowledgeContext
async def query_troubleshooting(query: KnowledgeQuery) -> TroubleshootingContext
```

输入输出已经足够支持第一阶段最小闭环，不应新增第二套 DTO 或改变签名。Runtime 的实际调用顺序是先 `resolve_product`，再构造携带 `ProductContext` 的 `KnowledgeQuery`，随后查询产品知识和排障知识。

## 5. 当前 Skill Runtime 能力

现有能力可直接复用：

- 递归发现 `skill.toml`；
- Pydantic 校验 Manifest，禁止未知字段；
- 禁止绝对入口和 `..` 路径逃逸；
- 校验 Core API；
- Product Plugin 入口必须是 JSON；
- 读取入口并计算 SHA-256；
- 内存 refresh/install/uninstall/list；
- 按 `product + product_version + skill_type` 精确解析；
- 未找到时抛出 `SkillNotInstalledError`。

它不理解产品知识内容，这是正确边界。内容语义校验和标准化应留在 Knowledge Engine。

## 6. 当前缺失能力

按实施优先级排列：

1. **插件内容 Schema**：当前只有通用 Manifest，缺少 Knowledge 内部的 Product/Troubleshooting payload model。
2. **一致性校验**：入口内容中的 product/version/component 与 Manifest 尚未交叉校验。
3. **明确解析错误**：未知产品、未知版本、缺 PRODUCT、缺 TROUBLESHOOTING、内容损坏目前未形成稳定领域错误分类。
4. **完整版本唯一性**：Registry 的 scope key 把整个版本列表拼接后比较，不能拒绝 `[1.0, 2.0]` 与 `[2.0]` 的重叠声明；相同名称不同 scope 也可能覆盖。
5. **Normalizer**：当前字段拼装位于 Adapter 方法内，尚未成为可独立测试的标准化组件。
6. **完整来源追踪**：KnowledgeContext 有 `RawReference`；ProductContext/TroubleshootingContext 没有 reference 字段，只能在不改变 Contract 的前提下使用 `source + metadata` 保存插件名、版本、入口 URI 和 digest。
7. **真实替换 E2E**：现有 Fake E2E 的 `ProblemContext.environment` 没有 `product/version`，不能直接交给当前插件 Resolver。
8. **Fixture 语义**：当前 TestProduct 1.0 提到重试和幂等要求，但没有完整表达指定的“timeout -> retry -> duplicate create risk”测试已知问题。
9. **查询选择策略**：当前 PRODUCT 查询返回该插件全部 facts，没有按功能或问题做复杂检索。MVP 可以保持有界全量返回，但必须写清 limitation，不能伪装成语义搜索。

## 7. 当前边界问题与冲突

### 没有发生的边界问题

- Knowledge 未 import Playwright 或 crawler；
- Core 未 import Skill Runtime 或具体 Product Skill；
- Reasoning 未读取插件文件；
- 插件原始 JSON 未跨越 KnowledgePort；
- Knowledge domain/contracts/ports 未 import LangChain；
- 没有真实 V7R2 数据或官网采集逻辑进入 Core。

### 需要处理但不应直接重构的冲突

1. 文档称“Plugin 内容必须校验”，但当前 Loader 只验证 Manifest/文件边界，Knowledge Adapter 只做运行时字典取值。
2. 任务书要求 RealKnowledgeEngine，当前公开类名是 `PluginKnowledgeEngine`。不应另建一套并行实现；实施时应将现有类强化为 canonical Real 实现，并仅在需要兼容时保留薄别名。
3. `KnowledgeService` 把所有非 `KnowledgeError` 包装为 retryable `KnowledgeDependencyError`。未知产品/版本通常不是瞬时依赖故障，需要先定义领域错误语义，再决定 HTTP/Runtime 映射。
4. `TroubleshootingContext` 当前表达“已执行动作、观察结果、workaround、约束”，不能完整承载插件中的“故障→症状→原因→操作→验证”知识。MVP 不修改冻结 Contract，也不能把“建议操作”伪装成 `actions_taken`；较丰富的知识只能先保留在插件内部，待 Contract 正式演进。
5. `ProblemContext.environment` 中的 `product/version` 是当前唯一显式解析依据。MVP 应保持确定性精确解析，不引入模糊匹配或 LLM 猜测。

## 8. Crawler 与具体产品知识审计

审计未发现：

- `src/ops_agent/knowledge/` 中的 crawler 实现；
- Playwright 依赖；
- Runtime 时官网爬取；
- V7R2 标识或真实产品知识；
- Tool Skill 混入 `skills/builtin/`；
- 外部 Crawler Skill 被复制进仓库。

Fake 和 TestProduct 内容均明确标记为合成测试数据，可以保留。

## 9. RealKnowledgeEngine 建议结构

采用最小演进，不引入第二套 Skill Runtime：

```text
src/ops_agent/knowledge/
├── domain/
│   ├── plugin_specs.py       # Knowledge 内部的插件内容 Pydantic Schema
│   └── errors.py             # 未知产品/版本、缺失配对、内容无效
├── service/
│   ├── main.py               # 保留 KnowledgeService 外部模块入口
│   └── normalizer.py         # 内部 Spec -> 冻结 Context
├── adapters/
│   └── plugin.py             # 现有实现强化为 canonical Real 插件实现
└── ports/
    └── __init__.py           # 继续只重导出 KnowledgePort
```

建议职责：

- Real/Plugin Knowledge 实现：协调 Resolver、payload 校验和 Normalizer，直接满足 `KnowledgePort`；
- Skill Runtime：只负责发现、文件安全、生命周期和精确候选选择；
- Product/Troubleshooting payload model：只定义插件入口内容，不成为新的跨模块 Contract；
- Normalizer：构造公共 Contract，统一 correlation、source、metadata、RawReference 和 limitation；
- KnowledgeService：保持健康检查、启停和模块错误边界，不负责插件语义。

若需要公开 `RealKnowledgeEngine` 名称，应从现有 `PluginKnowledgeEngine` 演进或提供兼容导出，禁止保留两套不同业务逻辑。

## 10. Product Skill Plugin 建议结构

Manifest 继续使用现有 `SkillManifest`：

```text
test-product-v1/product/
├── skill.toml
└── product.json
```

`product.json` 建议由 Knowledge 内部 `ProductSkillSpec` 校验，最小字段分组为：

```text
schema_version
product_context
features[]
retry_behavior
known_issues[]
limitations[]
```

其中：

- `product_context` 提供公共 ProductContext 所需业务字段；
- `features` 至少含 `create-order`；
- `retry_behavior` 说明 1.0 的自动重试能力和边界；
- `known_issues` 含 timeout → retry → duplicate create risk；
- 所有内容均为 TestProduct 合成数据；
- `product_context.product_name/product_version` 必须与 Manifest 的 product/product_versions 一致；
- Normalizer 将适用事实转换成 `KnowledgeContext.facts`，不会把插件原始对象暴露给 Runtime。

第一阶段不实现全文检索、向量检索、Markdown 执行、模板脚本或动态 Python 插件代码。

## 11. Troubleshooting Skill Plugin 建议结构

```text
test-product-v1/troubleshooting/
├── skill.toml
└── troubleshooting.json
```

内部 `TroubleshootingSkillSpec` 建议表达：

```text
schema_version
product
product_versions[]
faults[]:
  id
  symptoms[]
  possible_causes[]
  recommended_actions[]
  validation_steps[]
  known_workarounds[]
  constraints[]
```

MVP 只把当前公共 Contract 能准确表达的 `known_workarounds` 和 `constraints` 输出为 `TroubleshootingContext`。不得把尚未执行的 recommended action 写入 `actions_taken`，也不得把预期 validation 写成 `observed_results`。其余结构为插件内部知识，后续需要通过兼容 Contract 扩展或 v2 才能跨模块消费。

## 12. Test Fixture 设计

### TestProduct 1.0

- 产品：`TestProduct`
- 版本：`1.0`
- 组件：`create-api`
- 功能：`create-order`
- 行为：客户端在超时后最多自动重试一次；安全重试依赖服务端幂等。
- 已知问题：首次请求已成功但响应延迟，客户端重试；当创建接口未执行幂等去重时，可能重复创建。
- Troubleshooting：核对相同业务标识的请求时间线、首次提交结果和第二次创建；临时 workaround 为关闭自动重试或启用幂等保护。
- limitation：仅测试，不能连接生产系统或代表真实产品。

### TestProduct 2.0

- 保留独立 PRODUCT fixture；
- 使用不同 expected behavior/facts，证明 1.0 数据不会泄漏；
- 若将“Product + Troubleshooting 完整配对”作为 Real Engine 前置条件，则补充 2.0 TROUBLESHOOTING fixture；否则明确测试该版本缺失 Troubleshooting 时的错误。

### 非法 Fixture

建议在测试临时目录动态创建，不长期增加大量坏文件：

- Manifest 缺少 product/version；
- 入口逃逸或不存在；
- core_api 不兼容；
- Manifest 与 payload 产品/版本不一致；
- payload 缺字段或有未知字段；
- 两个插件声明重叠产品版本。

## 13. 需要新增或修改的文件

### 建议新增

- `src/ops_agent/knowledge/domain/plugin_specs.py`
- `src/ops_agent/knowledge/service/normalizer.py`
- `tests/knowledge/test_product_resolution.py`
- `tests/knowledge/test_version_isolation.py`
- `tests/knowledge/test_product_knowledge.py`
- `tests/knowledge/test_troubleshooting.py`
- `tests/knowledge/test_real_knowledge_port_contract.py`
- `tests/e2e/test_real_knowledge_incident_flow.py`

### 建议最小修改

- `src/ops_agent/knowledge/adapters/plugin.py`：使用内部 Spec 和 Normalizer，形成 Real 实现；
- `src/ops_agent/knowledge/adapters/__init__.py`：稳定公开入口；
- `src/ops_agent/knowledge/domain/errors.py` 与 `domain/__init__.py`：明确错误分类；
- `src/ops_agent/knowledge/service/main.py`：只在错误分类需要时调整包装策略；
- `src/ops_agent/skill_runtime/registry.py`：修正 name/scope/版本重叠唯一性；
- `src/ops_agent/skill_runtime/resolver.py`：如验收需要，区分未知产品与未知版本；
- `src/ops_agent/skill_runtime/validator.py`：只补通用 Manifest/package 规则，不加入产品知识语义；
- `tests/fixtures/product-skills/test-product-v1/**`：补齐指定合成 Case；
- `tests/fixtures/product-skills/test-product-v2/**`：补齐隔离或缺失配对场景；
- `docs/modules/03-knowledge.md`、`docs/interfaces/04-skill-plugin-spec.md`：实现完成后同步冻结实际规则。

任何对 `skill_runtime` 的修改都必须保持通用性，并与其模块负责人协作；不能把 TestProduct 规则写进 Generic Runtime。

## 14. 明确不能修改的文件或范围

本阶段不得为了让测试通过而修改：

- `src/ops_agent/contracts/**` 中现有冻结 Contract；
- `src/ops_agent/ports/engines.py` 的 KnowledgePort 签名；
- `src/ops_agent/core/**`；
- `src/ops_agent/reasoning/**`；
- `src/ops_agent/investigation/**`；
- `src/ops_agent/reproduction/**`；
- `skills/builtin/**`；
- 现有 `FakeKnowledgeEngine` 固定语义；
- `tests/e2e/test_fake_incident_flow.py` 的既有 Fake 基线；
- 外部 V7R2 Product Skill；
- 外部 Playwright Crawler/Tool Skill。

若冻结 Contract 的表达能力成为阻塞，应记录后续 Contract 演进需求，不用 `metadata` 偷渡或扭曲现有字段语义。

## 15. 测试计划

严格测试优先。第一批测试应先失败，再做最小实现。

| 验收项 | 建议测试 |
|---|---|
| Product Plugin 正常发现 | 从 fixture root refresh 后精确列出 PRODUCT |
| Product/Version 正常解析 | TestProduct/1.0 返回对应 package |
| 未知 Product | 明确的非静默错误，消息含产品和版本 |
| 未知 Version | 与未知产品可区分，不回退到 1.0/2.0 |
| 多版本隔离 | 1.0 与 2.0 输出不同且无事实串线 |
| Product Skill 加载 | payload 通过 ProductSkillSpec，Manifest/内容一致 |
| Troubleshooting 加载 | 类型隔离并通过 TroubleshootingSkillSpec |
| Manifest 校验 | 路径、core_api、必填 scope、重复 name、重叠版本 |
| 来源追踪 | URI、digest、skill name/version/type/product version 可追溯 |
| KnowledgeContext Schema | `model_validate`、JSON round trip、schema_version=1.0 |
| Port 兼容 | `isinstance(real_engine, KnowledgePort)` 且三个 async 方法通过共享 contract test |
| Real E2E | Real Knowledge + 其余 Fake + 原 Runtime 到 COMPLETED |
| 边界守护 | Knowledge 无 crawler/Playwright；Core/Reasoning 不读插件 |

E2E 输入应新增一个包含 `environment.product=TestProduct`、`environment.version=1.0` 的 Incident。Runner、Runtime、FakeReasoning、FakeInvestigation、FakeReproduction 不做定制修改，只通过构造器注入 Real Knowledge 实现。

建议验证命令：

```bash
.venv/bin/pytest tests/knowledge tests/skill_runtime -q
.venv/bin/pytest tests/contracts -q
.venv/bin/pytest tests/e2e/test_real_knowledge_incident_flow.py -q
.venv/bin/pytest tests/e2e/test_fake_incident_flow.py -q
.venv/bin/pytest tests/architecture -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/pytest
```

## 16. 实施顺序

1. 先新增验收测试：正常解析、未知产品/版本、版本隔离、非法 Manifest/payload、来源追踪和 Real E2E。
2. 定义 Knowledge 内部 `ProductSkillSpec` / `TroubleshootingSkillSpec`，不改变公共 Contract。
3. 修正 Generic Registry 的名称唯一性和版本范围重叠校验；如必要，增加通用解析错误细分。
4. 实现独立 Normalizer，冻结从内部 Spec 到公共 Context 的映射和 provenance。
5. 强化现有 `PluginKnowledgeEngine` 为 canonical Real 实现，避免并行重复实现。
6. 调整 TestProduct fixture，使 1.0 完整表达 create-order/retry/known issue，并验证 2.0 隔离。
7. 运行 Knowledge/Skill Runtime 专项测试并修复。
8. 使用原 Runner 注入 Real Knowledge，完成全流程 E2E；原 Fake E2E 必须保持不变且继续通过。
9. 运行 Contracts、架构守护、ruff、mypy 和全量 pytest。
10. 实际规则稳定后更新模块和 Plugin Spec 文档，停止，不接入真实 V7R2 资产。

## 17. MVP 完成标准

同时满足以下条件才算完成：

1. TestProduct 1.0 PRODUCT/TROUBLESHOOTING 插件可发现、校验、加载；
2. `ProblemContext` 中明确的产品/版本可被确定性解析；
3. 未知产品、未知版本和不完整插件返回明确错误，绝不跨版本回退；
4. Manifest 与 payload 的产品、版本和类型一致；
5. 输出为冻结的 ProductContext、KnowledgeContext、TroubleshootingContext；
6. 来源至少包含插件名、插件版本、入口 URI 和 SHA-256 digest；
7. TestProduct 1.0/2.0 严格隔离；
8. Real Knowledge 实现满足 `KnowledgePort`；
9. Real Knowledge + Fake Reasoning/Investigation/Reproduction 经原 Core Runtime 到达 COMPLETED；
10. 原 Fake E2E、Contracts、架构测试、ruff、mypy 和全量测试全部通过；
11. 仓库中没有真实 V7R2 内容、crawler 或 Runtime 官网访问；
12. 没有修改 Core Runtime、其他 Engine、冻结 Contract 或 Built-in Skill。

## 18. 当前风险

1. **Contract 表达力**：TroubleshootingContext 无法完整输出“原因/建议操作/验证步骤”；不得用错误字段强塞，后续可能需要兼容扩展或 v2。
2. **错误路由**：KnowledgeService 当前会把多数插件错误包装为 retryable dependency error，可能导致 Runtime 对配置错误无效重试。
3. **版本歧义**：Registry 当前对重叠 `product_versions` 检测不足，需要测试先行修复。
4. **内容一致性**：恶意或错误插件可以声明 TestProduct/1.0、内容却写另一个产品，当前未拒绝。
5. **查询精度**：MVP 返回插件内适用的有界事实，不是搜索系统；若 fixture 增大，需要显式索引/过滤策略。
6. **插件信任**：签名、远程下载、持久安装、权限和供应链校验不在 v0.2 范围，不能将当前文件加载器直接等同生产插件市场。
7. **外部兼容性**：现有 Manifest/Payload Spec 尚未用真实外部 V7R2 Skill 验证；接入前需要单独 compatibility adapter/test，而不是修改 Core 去迎合单一资产。
8. **来源字段限制**：只有 KnowledgeContext 原生携带 RawReference；其他 Context 的 provenance 暂存于允许扩展的 metadata，消费者必须按文档读取而不能依赖未冻结的私有键。
9. **产品识别范围**：第一阶段只接受显式产品/版本提示；别名、版本范围、自动检测和冲突消解应另立需求。
10. **职责协作**：Generic Skill Runtime 由 Runtime 负责人共同维护；Knowledge 只能提出通用修正，不能把产品语义下沉进去。

## 19. 方案编制轮明确未实施

方案编制轮只完成阅读、代码审计、现状测试和实施方案文档，当时没有修改 Python 业务代码、测试、Fixture、Contract、Port、Runtime、Skill 或 MCP，也没有接入任何真实 Product Skill、Crawler、网络或外部系统。

## 20. 第一阶段实施结果

确认后已按测试优先完成：Knowledge 内部 payload Schema、`KnowledgeNormalizer`、`RealKnowledgeEngine`、明确产品/版本错误、Registry 名称与版本重叠校验、TestProduct 1.0 合成知识、TestProduct 2.0 版本隔离，以及 Real Knowledge + 三个 Fake Engine 的完整 Runtime E2E。公共 Contract、KnowledgePort、Core Runtime、其他 Engine、Built-in Skill 与原 Fake E2E 均未修改。
