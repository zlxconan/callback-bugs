# 张龙兴 — Knowledge Engine 开发任务书

> 开发前先阅读根目录 `AGENTS.md` 与本文件。技术栈统一：Python 3.11+ / FastAPI / LangChain / Pydantic v2。

## 1. 模块定位

解决：**当前产品、当前版本到底应该怎样工作，以及有哪些已知故障和标准排障方式。**

核心能力：Product Skill Plugin Spec、Troubleshooting Skill Plugin Spec、Product/Version Resolver、Plugin Adapter、Knowledge Normalizer、来源追溯和版本隔离。

不负责：根因推理、现场取证、故障注入、Runtime 流程控制、产品文档爬虫、Playwright Crawler Skill、具体 V7R2 Skill 或真实产品知识内置。

## 2. 代码边界

主要负责：

```text
src/ops_agent/knowledge/
src/ops_agent/skill_runtime/       # 与连延斌协作维护通用规范
src/ops_agent/integrations/mcp/knowledge/  # 可选 KnowledgePort 传输
tests/knowledge/
tests/fixtures/product-skills/     # 只能放合成测试产品
docs/modules/03-knowledge.md
```

不得直接修改 `reasoning/`、`investigation/`、`reproduction/`、`core/runtime/`。

## 3. 必须实现的接口

以仓库现有定义为准，至少实现：

```python
KnowledgePort.resolve_product(...)
KnowledgePort.query_product_knowledge(...)
KnowledgePort.query_troubleshooting(...)
```

目标：`FakeKnowledgeEngine -> RealKnowledgeEngine`，替换后其他模块无需修改。

## 4. 输入/输出

主要输入：`ProblemContext`、`KnowledgeQuery`。

主要输出：`ProductContext`、`KnowledgeContext`、`TroubleshootingContext`。

输出必须体现：product、version、component、expected behavior、版本适用事实、source/reference、limitations、schema_version、incident_id/request_id。

禁止直接把整篇 Markdown 当跨模块输出。

## 5. 第一阶段 MVP

只做最小插件消费闭环：

```text
TestProduct / Version 1.0
├─ create-order
├─ retry behavior
└─ known issue: timeout -> retry -> duplicate create risk
```

验收要求：

1. 安装合成 TestProduct Product/Troubleshooting Plugin Fixture。
2. Resolver 按产品/版本精确路由，并拒绝未知版本。
3. Knowledge Adapter 输出带来源和 digest 的标准 Context。
4. RealKnowledgeEngine 可替换 FakeKnowledgeEngine。
5. 其余三个 Engine 继续 Fake 时，完整 E2E 通过。

## 6. 外部资产边界

现有 V7R2 Product Skill 是外部插件资产；现有 Playwright Crawler Skill 是外部 Tool Skill。两者都不复制、迁入或重新实现。Crawler/Parser/Skill Builder 负责知识生产，Knowledge Engine 只消费已发布 Package。

## 7. 对接关系

| 对接模块 | 你提供 | 对方提供 | 联调标准 |
|---|---|---|---|
| Core Runtime | `KnowledgePort` 实现 | Runtime 调用上下文 | 可直接替换 FakeKnowledge |
| Reasoning | `KnowledgeContext`、`TroubleshootingContext` | 根因假设所需知识需求 | Reasoning 不读取内部存储 |
| Investigation | 组件/版本/已知故障建议的证据类型 | 真实 Evidence | 知识不能冒充现场事实 |
| Reproduction | 版本能力、前置条件、已知复现步骤 | ExperimentResult | 实验遵守版本条件 |
| Integration | Plugin Spec / KnowledgeContext | Agent Host 包装验证 | Host 不读取插件内部文件 |

## 8. 测试要求

至少覆盖：产品识别、版本识别、未知产品、未知版本、版本隔离、同一故障不同版本适用性、来源追溯、Contract Schema、异常处理。

建议测试文件：

```text
tests/knowledge/test_product_resolution.py
tests/knowledge/test_version_isolation.py
tests/knowledge/test_product_knowledge.py
tests/knowledge/test_troubleshooting.py
tests/knowledge/test_real_knowledge_port_contract.py
```

## 9. 独立验收

实际执行：

```bash
pytest tests/knowledge -q
pytest tests/contracts -q
pytest tests/e2e/test_fake_incident_flow.py -q
ruff check .
mypy src
```

最终验收：**不改其他 Engine 的情况下，RealKnowledgeEngine 能直接替换 FakeKnowledgeEngine，并让完整 E2E 继续通过。**

## 10. 交付物

Real/PluginKnowledgeEngine、Product/Troubleshooting Plugin Spec、Resolver/Normalizer、Knowledge Adapter、合成测试 Fixture、测试、模块文档和验证记录。不得交付真实 V7R2 内容或 crawler。
