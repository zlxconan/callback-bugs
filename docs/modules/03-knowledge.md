# Knowledge Engine Boundary v0.2

## 职责

Knowledge Engine 负责：

- Product Skill Plugin / Troubleshooting Skill Plugin 发现接口；
- 产品与版本精确路由；
- 插件解析和来源追踪；
- 版本隔离；
- 将插件内容标准化为 ProductContext、KnowledgeContext、TroubleshootingContext；
- 通过 KnowledgePort 向 Runtime 提供结果。

`RealKnowledgeEngine` 是第一阶段真实插件消费实现：它使用 Generic Skill Resolver 加载外部 package，通过 Knowledge 内部的 `ProductSkillSpec` / `TroubleshootingSkillSpec` 校验内容，再由 `KnowledgeNormalizer` 转换为冻结 Contract。`PluginKnowledgeEngine` 仅保留为同一实现的兼容名称，不存在第二套逻辑。

## 非职责

Knowledge Engine 不实现产品官网 crawler、Playwright Crawler Skill、具体 V7R2 Skill，不内置真实产品知识，也不在 Incident Runtime 时实时爬官网。Crawler/Parser/Builder 属于外部知识生产工具链。

## 输入输出

| 操作 | 输入 | 输出 |
|---|---|---|
| resolve_product | ProblemContext | ProductContext |
| query_product_knowledge | KnowledgeQuery | KnowledgeContext |
| query_troubleshooting | KnowledgeQuery | TroubleshootingContext |

Product Plugin 原始文件不得跨出 Knowledge Adapter。Reasoning 只能消费上述标准 Contract。

## 依赖关系

```text
Runtime -> KnowledgePort -> Knowledge Service/Adapter
                           -> SkillResolver
                           -> SkillRegistry/Loader/Validator
                           -> installed Product Plugin
                           -> KnowledgeContext
```

模块化单体默认进程内调用。`knowledge-mcp` 只在远程部署时作为 KnowledgePort Adapter，不是产品知识载体。

## Plugin Spec

Product/Troubleshooting manifest 必须声明类型、产品、适用版本、插件版本、Core API 和安全相对入口。真实插件位于外部 Product Skill Repository；本仓库仅保留 `tests/fixtures/product-skills/` 合成数据。

插件入口 payload 使用 Knowledge 内部 Pydantic model，`extra="forbid"`。PRODUCT payload 包含 product context、features、retry behavior、known issues 和 limitations；TROUBLESHOOTING payload 包含产品范围和按故障组织的 symptom/cause/action/validation/workaround/constraint。内部 payload model 不是新的跨模块 Contract，原始内容不会越过 KnowledgePort。

Resolver 使用产品、版本和 Skill 类型精确匹配，不允许跨版本回退。Registry 同时拒绝重复 manifest name 和重叠的 `type + product + product_version` 注册。未知产品、未知版本和无效 payload 由 Knowledge 领域错误明确区分。

来源追踪规则：`KnowledgeContext.references` 保存入口 URI、SHA-256 和 media type；三个输出 Context 的 `metadata` 保存 skill name/version/type、产品版本范围、入口 URI 和 digest。由于冻结的 ProductContext/TroubleshootingContext 没有 RawReference 字段，本阶段不修改公共 Contract。

## 测试与 Done

- 未安装产品/版本返回明确错误；
- 同一产品不同版本严格隔离；
- PRODUCT 与 TROUBLESHOOTING 类型不混用；
- RawReference 包含入口 URI 与 digest；
- PluginKnowledgeEngine 结构化满足 KnowledgePort；
- RealKnowledgeEngine + Fake Reasoning/Investigation/Reproduction 通过原 Core Runtime 到达 COMPLETED；
- Knowledge 不 import Playwright/crawler；
- FakeKnowledgeEngine 和既有 Fake E2E 保持稳定。

第一阶段 MVP 已使用 TestProduct 1.0 验证 create-order、客户端超时重试和缺少幂等时的 duplicate create risk。TestProduct 2.0 只用于 PRODUCT 版本隔离测试；它不代表真实产品，也没有在本阶段补充 Troubleshooting package。

负责人目录：`src/ops_agent/knowledge/`、`src/ops_agent/skill_runtime/` 的接口协作、`tests/knowledge/` 与测试插件 Fixture。不得提交真实产品 Skill 内容。
