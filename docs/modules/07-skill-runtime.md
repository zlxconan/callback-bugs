# Generic Skill Runtime v0.2

`ops_agent.skill_runtime` 是产品无关的插件生命周期基础设施。

## 组件

- `manifest.py`：SkillType 和 SkillManifest；
- `loader.py`：递归发现与入口内容加载；
- `validator.py`：兼容性、路径和重复范围校验；
- `registry.py`：发现、安装、卸载和类型索引；
- `resolver.py`：产品/版本/类型精确路由。

## 非职责

不保存真实产品知识，不运行 crawler/parser，不执行 MCP，不产生 KnowledgeContext，不参与 Incident 状态机。Tool Skill 不注册。

## 调用

```text
bootstrap/Knowledge Adapter -> SkillResolver -> Registry -> Loader/Validator
                                            -> installed Plugin package
```

Core Runtime 不直接调用 Generic Skill Runtime。Built-in Method Skill 的 Agent Host Packaging 仍由 `ops_agent.skills` 负责，但两者共享 `SkillType` 分类。

## 安装配置与装配

`SkillInstallationConfig` 集中读取三个现有部署值：

- `OPS_AGENT_BUILTIN_SKILLS_PATH`：可选，默认 `skills/builtin`；
- `OPS_AGENT_PRODUCT_SKILLS_PATH`：Real Knowledge 装配必填；
- `OPS_AGENT_SKILL_CORE_API`：可选，默认 `1.0`。

`ops_agent.bootstrap.skills.build_skill_installation()` 是组合根：启动时读取一个 Built-in 根目录和一个 Product Plugin 根目录，使用相同的 Core API Validator，调用一次 `SkillRegistry.refresh()`，再把 Resolver 注入 `RealKnowledgeEngine`。当前没有多根目录聚合、文件监视或运行中热加载。

Loader 只读取文件；Registry 的 install/uninstall 只改变进程内索引，不写入或删除插件目录。部署时两个目录均应只读，其中 Product Plugin 根必须通过外部 volume 提供。预检查入口为 `scripts/verify_skill_installation.py`。
