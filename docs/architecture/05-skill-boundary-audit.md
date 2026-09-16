# Skill Boundary Audit — Baseline v0.2

> 审计日期：2026-09-16  
> 范围：README、architecture/interfaces/modules、六人任务书、src、skills、MCP

## 1. 审计结论

| 检查项 | 审计结果 | 对齐动作 |
|---|---|---|
| 具体产品/版本知识写入 Core | 未发现真实资产；Fake/MVP 含明确合成知识 | 保留测试 Fake，并在文档声明不代表真实产品 |
| V7R2 硬编码 | 未发现 | 明确外部 V7R2 Skill 不迁入仓库 |
| product-doc-crawler 在 Knowledge | 未发现 | 增加架构守护测试和外部 Tool Skill 边界 |
| Knowledge 依赖 Playwright crawler | 未发现 | 增加禁止 import 守护测试 |
| Tool/Built-in Skill 混放 | 未发现 Tool Skill，但原 Skill 根目录未分类 | 六个方法 Skill 迁入 `skills/builtin/` |
| Product 与 Built-in 未区分 | 发现：product-knowledge/troubleshooting 被当作 Canonical Built-in | 从 Core Built-in 移除，改由 Product Plugin Spec 表达 |
| Reasoning 读取插件文件 | 未发现 | 增加静态守护；只允许 KnowledgeContext |
| Runtime 操作 Product Skill | 未发现 | Core Runtime 继续不 import skill_runtime/插件实现 |
| MCP 承担 Planner/Reflection | 未发现 | 文档冻结禁止职责 |
| Generic Skill Runtime | 缺失 | 新增 manifest/loader/validator/registry/resolver |
| Knowledge Plugin 查询 | 缺失 | 新增最小 PluginKnowledgeEngine 与测试 Fixture |

## 2. 保留的稳定资产

未重写或删除 Core Runtime、Contracts v1、Ports v1、四个 Engine Protocol、MCP Registry、Fake Engines、Fake E2E、External/Local Agent Adapter。现有 `knowledge-mcp` 代码保留为 KnowledgePort 的可选传输适配。

## 3. 目录迁移

迁移前：八个 Skill 平铺于 `skills/`。  
迁移后：六个产品无关方法 Skill 位于 `skills/builtin/`；原通用 `product-knowledge` 与 `troubleshooting` 不再作为 Core Built-in。真实产品 Skill 不进入仓库；测试插件只位于 `tests/fixtures/product-skills/`。

## 4. 新增边界

- `SkillType`: BUILTIN_METHOD / PRODUCT / TROUBLESHOOTING；
- Plugin manifest 明确 product、product_versions、version、entrypoint、core_api；
- Loader 只读 package；Validator 防止路径逃逸与不兼容；Registry 管理发现/安装/卸载索引；Resolver 精确匹配产品版本；
- Knowledge Adapter 是唯一把 Product Plugin JSON 转为公共 Knowledge Contract 的位置。

Tool Skill 当前有意不进入 Generic Incident Registry。

## 5. 已知例外与风险

- FakeKnowledgeEngine 中的订单版本是明确标记的合成测试知识，不是可安装 Product Plugin；后续可迁移 Fake 数据，但本次不破坏 Fake E2E。
- Generic Registry v0.2 是进程内、只读发现与内存生命周期，不含签名、远程仓库、持久化安装目录或依赖求解。
- Manifest Spec 尚未与外部 V7R2 package 做真实兼容验证。
- 真实 CodeBuddy/Codex Host、真实 Product Repository、真实 MCP transport 均未验证。
