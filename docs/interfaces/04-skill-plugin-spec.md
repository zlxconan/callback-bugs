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

## Entrypoint Payload

Manifest 是 Generic Skill Runtime 的通用元数据；入口内容由 Knowledge Engine 的内部 Pydantic Schema 校验，两者不能互相替代。

PRODUCT JSON v1：

```text
schema_version: "1.0"
product_context:
  product_name / product_version / component
  deployment_environment / expected_behavior / configuration
features[]: id / description
retry_behavior: enabled / max_retries / description
known_issues[]: id / description
limitations[]
```

TROUBLESHOOTING JSON v1：

```text
schema_version: "1.0"
product
product_versions[]
faults[]:
  id / symptoms[] / possible_causes[]
  recommended_actions[] / validation_steps[]
  known_workarounds[] / constraints[]
```

Payload 禁止未知字段。Manifest 的产品和适用版本必须与 payload 一致；不一致时 Knowledge Engine 返回 `KNOWLEDGE_PLUGIN_INVALID`。Troubleshooting 的建议操作和验证步骤不会被错误映射成公共 Contract 中表示历史事实的 `actions_taken` 或 `observed_results`。

## 生命周期和错误

Loader 发现、Validator 校验、Registry 建立内存索引、Resolver 按 product/version/type 解析。重复 manifest name、重叠产品版本范围、不安全入口、缺失入口或 Core API 不兼容均拒绝加载；未安装匹配 Package 抛出 `SkillNotInstalledError` 的明确产品或版本子类。

Registry 的 install/uninstall 只改变进程内索引，不删除外部 Repository 文件。远程下载、签名、信任链和持久化安装器不在 v0.2 范围。

## 消费边界

只有 Knowledge Adapter 读取 Product Plugin content，并转换为 ProductContext、KnowledgeContext 或 TroubleshootingContext。Reasoning、Runtime、Agent Host 和 MCP 不读取插件内部文件。

Tool Skill 不使用本 Spec，也不进入 Incident Runtime Registry。
