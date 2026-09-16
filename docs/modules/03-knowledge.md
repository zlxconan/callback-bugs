# Knowledge Engine Boundary v0.2

## 职责

Knowledge Engine 负责：

- Product Skill Plugin / Troubleshooting Skill Plugin 发现接口；
- 产品与版本精确路由；
- 插件解析和来源追踪；
- 版本隔离；
- 将插件内容标准化为 ProductContext、KnowledgeContext、TroubleshootingContext；
- 通过 KnowledgePort 向 Runtime 提供结果。

`PluginKnowledgeEngine` 是最小参考 Adapter：它使用 Generic Skill Resolver 加载外部 package，并在 Engine 边界转换为冻结 Contract。

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

## 测试与 Done

- 未安装产品/版本返回明确错误；
- 同一产品不同版本严格隔离；
- PRODUCT 与 TROUBLESHOOTING 类型不混用；
- RawReference 包含入口 URI 与 digest；
- PluginKnowledgeEngine 结构化满足 KnowledgePort；
- Knowledge 不 import Playwright/crawler；
- FakeKnowledgeEngine 和既有 Fake E2E 保持稳定。

负责人目录：`src/ops_agent/knowledge/`、`src/ops_agent/skill_runtime/` 的接口协作、`tests/knowledge/` 与测试插件 Fixture。不得提交真实产品 Skill 内容。
