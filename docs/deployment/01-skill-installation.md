# Skill Installation & Pre-deployment Configuration

> 基线：Architecture Baseline v0.2
> 范围：Skill 安装、发现、验证与部署前检查；不包含 Dockerfile

## 1. 三类 Skill

### Built-in Method Skills

Built-in Skill 属于 Core，与产品和版本无关，随应用版本一起发布。当前 canonical source 是仓库的 `skills/builtin/`：

- `incident-analysis`
- `hypothesis-generation`
- `evidence-planning`
- `reflection`
- `reproduction-planning`
- `rca-report`

开发默认路径是相对当前工作目录的 `skills/builtin`。容器部署约定路径为：

```text
/opt/ops-agent/skills/builtin/
```

Built-in Skill 应显式复制进未来的 Core Image，并以只读方式运行。当前 setuptools 配置只打包 `src/` 下的 Python package，不会自动把仓库根目录的 `skills/` 放进 wheel；未来镜像构建必须显式 COPY，但本步骤不创建 Dockerfile。

Built-in Skill 不放入 Product Skill Repository，也不通过 Product Plugin 生命周期管理。

### Product Plugin Skills

PRODUCT 和 TROUBLESHOOTING Skill 与具体产品和版本绑定。它们不进入 Core Image，不硬编码进 Python 源码，通过外部 Product Skill Repository 安装或挂载。

容器内约定根目录：

```text
/opt/ops-agent/plugins/product-skills/
```

Loader 会从该根目录递归查找所有 `skill.toml`。目录层级本身不参与路由；路由权威信息来自 Manifest 的 `skill_type + product + product_versions`。

### Tool Skills

`product-doc-crawler`、`fault-manual-parser`、`website-to-product-skill` 等属于外部 Knowledge Ingestion Tool。现有 Playwright 产品文档爬取 Skill 不复制进本仓库、不进入 Core Image、不进入 Incident Skill Registry，也不在 Incident 分析时执行。

```text
产品官网
  -> Crawler Tool Skill
  -> Playwright
  -> Product Skill Package
  -> Product Skill Repository

Product Skill Repository
  -> read-only mount
  -> Skill Runtime
  -> Knowledge Engine
```

Tool Skill 应部署在独立的 `tool-skill-repository` 或知识生产环境，其安装方式不属于本文运行时流程。

## 2. 部署拓扑

```text
Core Image
└── /opt/ops-agent/skills/builtin/       # 六个 Built-in，随镜像发布，只读
    └── 不包含任何 Product Skill

Host
└── /srv/ops-agent/product-skills/       # 外部 Product Skill Repository
              |
              | read-only volume
              v
Container
└── /opt/ops-agent/plugins/product-skills/
              |
              v
       SkillLoader -> SkillRegistry -> SkillResolver
                                      -> RealKnowledgeEngine
```

建议 volume mount：

```text
/srv/ops-agent/product-skills:/opt/ops-agent/plugins/product-skills:ro
```

`ro` 是部署要求。当前 Loader 只读文件，Registry 的 `install()` / `uninstall()` 只改变进程内索引，不会复制、覆盖或删除磁盘文件。

## 3. Product Skill 目录规范

推荐使用下面的稳定运维布局：

```text
product-skills/
└── <product-directory>/
    └── <product-version>/
        ├── product/
        │   ├── skill.toml
        │   └── product.json
        └── troubleshooting/
            ├── skill.toml
            └── troubleshooting.json
```

例如合成 TestProduct：

```text
tests/fixtures/product-skills/
├── test-product-v1/
│   ├── product/{skill.toml,product.json}
│   └── troubleshooting/{skill.toml,troubleshooting.json}
└── test-product-v2/
    └── product/{skill.toml,product.json}
```

目录名可以为部署友好的 slug，但 Manifest 中的 `product` 和 `product_versions` 必须与入口 payload 精确一致。禁止依赖目录名猜测产品版本。

## 4. Manifest 和 Payload 要求

每个 PRODUCT/TROUBLESHOOTING package 都必须有独立 `skill.toml`：

```toml
schema_version = "1.0"
name = "test-product-product-v1"
skill_type = "PRODUCT"
version = "1.0.0"
product = "TestProduct"
product_versions = ["1.0"]
entrypoint = "product.json"
core_api = "1.0"
```

规则：

- `name` 是全 Registry 唯一的小写 kebab-case；
- `skill_type` 只能是 `PRODUCT` 或 `TROUBLESHOOTING`；
- `version` 是插件 package SemVer，不是产品版本；
- `product` 使用精确、区分大小写的产品标识；
- `product_versions` 必须非空，且同类型插件不能声明重叠产品版本；
- `entrypoint` 必须是 package 内的安全相对 JSON 路径；
- `core_api` 当前必须与 `OPS_AGENT_SKILL_CORE_API` 一致，默认 `1.0`；
- PRODUCT payload 的 `product_name/product_version` 必须匹配 Manifest；
- TROUBLESHOOTING payload 的 `product/product_versions` 必须匹配 Manifest；
- payload 使用严格 Pydantic Schema，未知字段会被拒绝。

完整 payload 结构见 [Product Skill Plugin Spec](../interfaces/04-skill-plugin-spec.md)。

## 5. 运行时配置

当前只有以下 Skill 部署配置；没有隐藏配置文件或第二套设置系统：

| 环境变量 | 必填 | 默认值 | 用途 | 敏感 |
|---|---:|---|---|---:|
| `OPS_AGENT_BUILTIN_SKILLS_PATH` | 否 | `skills/builtin` | Built-in canonical root；容器中应显式设为 `/opt/ops-agent/skills/builtin` | 否 |
| `OPS_AGENT_PRODUCT_SKILLS_PATH` | 是 | 无 | 已挂载 Product Plugin Repository 根目录 | 否 |
| `OPS_AGENT_SKILL_CORE_API` | 否 | `1.0` | Manifest `core_api` 兼容校验 | 否 |

`.env.example` 的 Product 路径只用于开发和 TestProduct 验证。生产环境必须替换为外部挂载路径。Skill 路径不含密码、Token 或真实产品知识；未来 Repository 下载凭据不能放进 Manifest 或本文件。

当前明确限制：

- 只支持一个 Built-in 根和一个 Product Plugin 根；
- 进程启动时由组合根调用一次递归发现，没有文件 watcher 或自动热更新；
- 没有关闭发现的环境变量；Real Knowledge 装配始终执行一次 `refresh()`；
- 没有可写模式；文件读取是只读的，部署通过 `:ro` mount 强制；
- Knowledge Engine 不自行查找路径，而是由 `build_skill_installation()` 构造 Registry/Resolver 后注入。

## 6. 安装 Product Plugin

1. 在外部 Product Skill Repository 准备完整 package。
2. 在隔离目录检查 `skill.toml` 和 JSON payload，不要把真实资产复制到 Core 仓库。
3. 将 package 放到 `<product>/<version>/product` 或 `troubleshooting` 目录。
4. 确保运行用户对目录和文件有读取/遍历权限。
5. 以只读 volume 将 Repository 根挂载到容器。
6. 设置 `OPS_AGENT_PRODUCT_SKILLS_PATH` 指向容器内挂载根。
7. 运行本文第 10 节预检查。
8. 启动或重启应用，使组合根重新执行 `SkillRegistry.refresh()`。

安装不是把文件复制进 Core Image。当前 `SkillRegistry.install()` 只是内存索引操作，不是磁盘安装器。

## 7. 卸载 Product Plugin

1. 先确认没有新 Incident 需要该产品版本。
2. 从外部 Repository 的发布版本中移除目标 package，或切换 volume 到不含该 package 的版本。
3. 重启应用或重新构建进程内 Registry。
4. 用预检查确认该产品/版本返回明确的未安装错误。

`SkillRegistry.uninstall(name)` 只用于当前进程内索引，不删除文件，也不能代替 Repository 发布操作。

## 8. 更新插件版本

插件 package `version` 与产品版本是两个概念。更新同一产品版本的知识时：

1. 在 Repository staging 目录生成新的 package 内容；
2. 增加 Manifest 的 SemVer `version`；
3. 保持 `product/product_versions` 表达真实适用范围；
4. 执行预检查；
5. 原子切换 Host Repository 的发布目录或 volume；
6. 重启应用以刷新内存 Registry；
7. 检查 Knowledge 输出 metadata 中的 skill version 和 digest。

不要在正在运行的挂载目录内逐文件覆盖，否则一次递归发现可能读到混合版本。

## 9. 同产品多版本共存

不同产品版本使用独立 package 和唯一 Manifest name：

```text
product-a/
├── V7R2/product/...
├── V7R2/troubleshooting/...
├── V8R1/product/...
└── V8R1/troubleshooting/...
```

Resolver 使用精确 `product + product_version + skill_type` 路由，不做最近版本、通配符或模型记忆回退。同一个 `skill_type + product + product_version` 只能注册一次；重叠范围会使整个 Registry refresh 失败。

## 10. 安装预检查

开发环境 TestProduct：

```bash
export OPS_AGENT_BUILTIN_SKILLS_PATH="$PWD/skills/builtin"
export OPS_AGENT_PRODUCT_SKILLS_PATH="$PWD/tests/fixtures/product-skills"
export OPS_AGENT_SKILL_CORE_API="1.0"

.venv/bin/python scripts/verify_skill_installation.py \
  --product TestProduct \
  --version 1.0 \
  --comparison-version 2.0
```

成功时输出 JSON，验证：

1. 六个 Built-in Skill 可发现且名称集合准确；
2. Product Plugin 根目录存在；
3. 所有 Manifest、Core API、入口和重复范围合法；
4. PRODUCT/TROUBLESHOOTING Skill 能按 TestProduct 1.0 解析；
5. TestProduct 1.0/2.0 使用不同 package 和 digest；
6. 未安装产品返回明确错误；
7. RealKnowledgeEngine 能加载 Product 与 Troubleshooting 内容；
8. Incident Runtime 类型中不包含 Tool Skill。

脚本只读文件，不打印插件正文。`ok=true` 才表示预检查成功。生产使用时把三个 CLI 产品参数替换为外部 Repository 中一个具有 PRODUCT、TROUBLESHOOTING 和第二个 PRODUCT 版本的非敏感标识；参数不应包含密码或 Token。

## 11. 错误排查

| 错误/现象 | 原因 | 处理 |
|---|---|---|
| `OPS_AGENT_PRODUCT_SKILLS_PATH must point...` | 未设置 Product 根目录 | 设置为容器内只读 mount 路径 |
| `root does not exist or is not a directory` | 路径错误或 volume 未挂载 | 检查 Host 路径、mount 和权限 |
| `requires Core API ...` | Manifest `core_api` 不兼容 | 安装兼容 package；不要跳过 Validator |
| `entrypoint escapes its package` | 入口使用绝对路径或 `..` | 改为 package 内相对路径 |
| `entrypoint does not exist` | JSON 未发布完整 | 重新发布完整 package |
| `Duplicate Skill manifest name` | 两个 package 使用相同 name | 为每个 package 使用唯一名称 |
| `overlapping Skill product version` | 同一产品版本被同类型插件重复声明 | 保留唯一发布版本 |
| `KNOWLEDGE_PRODUCT_NOT_INSTALLED` | 没有匹配产品或 Skill 类型 | 检查精确 product、mount 和 Manifest |
| `KNOWLEDGE_PRODUCT_VERSION_NOT_INSTALLED` | 产品存在但版本不匹配 | 安装精确版本，禁止静默回退 |
| `KNOWLEDGE_PLUGIN_INVALID` | payload Schema 或 Manifest/payload 不一致 | 按 Plugin Spec 修复 package |
| Built-in set mismatch | Core Image 缺 Skill 或路径指错 | 检查镜像 COPY 和 Built-in path |

## 12. TestProduct 示例边界

`tests/fixtures/product-skills/` 只保存合成 TestProduct：

- 1.0：PRODUCT + TROUBLESHOOTING；
- 2.0：PRODUCT，用于版本隔离；
- 不代表任何真实产品行为；
- 不应作为生产知识挂载。

## 13. 真实 V7R2 Skill 放置方式

真实 V7R2 资产继续保存在外部 Product Skill Repository。推荐 Host 布局：

```text
/srv/ops-agent/product-skills/
└── <real-product-slug>/
    └── V7R2/
        ├── product/{skill.toml,<product-entrypoint>.json}
        └── troubleshooting/{skill.toml,<troubleshooting-entrypoint>.json}
```

Manifest 的 `product` 使用外部资产定义的精确产品标识，`product_versions=["V7R2"]`，payload 与之匹配。本文不提供、不复制也不推断真实 V7R2 内容。首次接入前必须单独进行 Spec 兼容验证。

## 14. 安装完成标准

- Core Image 只有 Built-in Skill；
- Product Repository 通过只读 volume 提供；
- Tool Skill 不在运行时目录；
- 路径配置可解析且根目录存在；
- Registry refresh 成功，无重复和版本重叠；
- 目标产品 PRODUCT/TROUBLESHOOTING 均可解析；
- 版本隔离和缺失插件行为通过；
- RealKnowledgeEngine 查询通过；
- 预检查输出 `ok=true` 后才允许启动 Incident 服务。
