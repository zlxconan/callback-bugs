# Product Skill Plugin Spec v0.2

权威实现：`ops_agent.skill_runtime.manifest.SkillManifest`。

## Manifest

```toml
schema_version = "1.0"
name = "test-product-product-v1"
skill_type = "PRODUCT" # PRODUCT | TROUBLESHOOTING
version = "1.0.0"
product = "TestProduct"
product_versions = ["1.0"]
entrypoint = "product.json"
core_api = "1.0"
```

| 字段 | 约束 |
|---|---|
| schema_version | 当前只接受 1.0 |
| name | 小写 kebab-case，全 Registry 唯一 |
| skill_type | PRODUCT 或 TROUBLESHOOTING；BUILTIN_METHOD 仅供 Core 内置目录 |
| version | Package SemVer，不等同产品版本 |
| product | 精确产品标识，Product Plugin 必填 |
| product_versions | 非空适用版本集合；Resolver 精确匹配且隔离 |
| entrypoint | Package 内安全相对路径，Product Plugin 当前使用 JSON |
| core_api | 与 Generic Skill Runtime 兼容版本 |

## Package

```text
product-skill-package/
  skill.toml
  product.json                  # PRODUCT
# 或
  troubleshooting.json         # TROUBLESHOOTING
```

Package 可来自外部 repository 或安装目录。Core 仓库只在 `tests/fixtures/product-skills/` 保存合成测试 Package。

## 生命周期和错误

Loader 发现、Validator 校验、Registry 建立内存索引、Resolver 按 product/version/type 解析。重复范围、不安全入口、缺失入口或 Core API 不兼容均拒绝加载；未安装匹配 Package 抛出 `SkillNotInstalledError`。

Registry 的 install/uninstall 只改变进程内索引，不删除外部 Repository 文件。远程下载、签名、信任链和持久化安装器不在 v0.2 范围。

## 消费边界

只有 Knowledge Adapter 读取 Product Plugin content，并转换为 ProductContext、KnowledgeContext 或 TroubleshootingContext。Reasoning、Runtime、Agent Host 和 MCP 不读取插件内部文件。

Tool Skill 不使用本 Spec，也不进入 Incident Runtime Registry。
