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
