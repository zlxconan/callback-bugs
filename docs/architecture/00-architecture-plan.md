# Ops Agent Architecture Baseline v0.2

> 状态：Boundary aligned
> 日期：2026-09-16
> 形态：Python 3.11+ 模块化单体

## 1. 项目定义

Ops Agent 是 Agent-independent 的智能问题分析与复现核心平台。Core 提供稳定协议、确定性流程、产品无关的方法论和工具执行接口；产品知识、环境观测和实验工具由外围插件接入。

Core 由 Contracts、Ports、Core Runtime、六个 Built-in Method Skills、Generic Skill Runtime、四个 Engine、MCP Interface 与 Agent Host Adapter 组成。Core 不包含真实产品知识、真实 V7R2 资产、产品文档爬虫或具体环境凭据。

## 2. 逻辑架构

```text
                 Agent Host
       CodeBuddy / Codex / Local Agent
                     |
          Built-in Method Skills
                     |
                Runtime MCP
                     |
                Core Runtime
          +----------+-----------+
          |          |           |
      Knowledge   Reasoning  Investigation
          |                       |
     Skill Runtime         Observability MCP
          |
 Product Plugin / Troubleshooting Plugin
                     |
                Reproduction
                     |
              Reproduction MCP
```

独立的知识生产链：

```text
产品官网 -> Crawler / Parser Tool Skill -> Playwright MCP
        -> Product Skill Package -> 外部 Product Skill Repository
```

知识生产链不在 Incident Runtime 内运行。Knowledge Engine 只消费已经安装、校验和版本化的 Plugin Package。

## 3. Skill 三分类

### Core Built-in Method Skills

位于 `skills/builtin/`，随 Core 发布，与产品和版本无关：`incident-analysis`、`hypothesis-generation`、`evidence-planning`、`reflection`、`reproduction-planning`、`rca-report`。

### Product Plugin Skills

类型为 `PRODUCT` 或 `TROUBLESHOOTING`，必须声明产品、适用版本、插件版本、Core API 兼容性和入口文件。真实插件存放在外部 Product Skill Repository，可独立安装、升级、卸载。

本仓库只包含规范、Runtime 和 `tests/fixtures/product-skills/` 下的合成测试插件。现有外部 V7R2 Product Skill 不复制、不迁入、不重新实现。

### Tool Skills

crawler、manual parser、PDF/website-to-skill 等属于离线知识生产工具。它们可以调用 Playwright MCP，但不注册到 Incident Skill Runtime，也不进入 `ops_agent.knowledge`。现有外部 Playwright crawler 不复制或重新实现。

## 4. MCP 分类

- Runtime MCP：Core 的 Incident start/next/submit/get-state/finish。
- Observability MCP：Trace、Logs、Metrics、K8s、Change、Topology，按环境插件化。
- Code MCP：代码搜索、调用图、堆栈定位，只产生 Evidence。
- Reproduction MCP：Browser、API、Shell、网络故障、负载和 Chaos 工具，按工具/环境插件化。
- Knowledge Engine MCP Adapter：仅在远程部署时映射 KnowledgePort；它不是 Product Skill 仓库，也不承载产品内容。

MCP 不实现 Planner、Hypothesis、Reflection、Skill 方法论或状态机。

## 5. 模块职责

- Core Runtime：唯一持有 IncidentState、状态转换、Retry/Timeout、Loop、Policy、Human Approval、Audit 和停止条件；不加载具体 Product Plugin。
- Generic Skill Runtime：负责 Manifest、Loader、Validator、Registry、Resolver 和内存生命周期；不理解产品事实，不执行 Tool Skill，不推进 Incident。
- Knowledge：发现产品/版本对应的 Product/Troubleshooting Plugin，解析并标准化为 Knowledge Contracts；不爬官网、不内置真实知识。
- Reasoning：只消费标准 KnowledgeContext/TroubleshootingContext；不得读取插件文件。
- Investigation：通过 Tool Port 或 Observability MCP 获取数据并标准化为 Evidence；Reasoning 不直接调用观测 MCP。
- Reproduction：执行已批准 ExperimentPlan；Playwright、Toxiproxy、mitmproxy、k6、Chaos Mesh 均为 Tool Adapter/MCP。

## 6. 依赖规则

```text
contracts <- ports <- core runtime
     ^          ^         |
     |          |         +-> Engine Ports
     |          +------------ Engine Services -> Tool Ports -> Adapters/MCP
     +----------------------- Agent/Integration Adapters

Knowledge Adapter -> Skill Runtime -> installed external plugin package
Reasoning ----------> KnowledgeContext only
```

contracts 只依赖标准库/Pydantic；ports 只依赖 contracts/typing；core 只依赖 contracts、ports 和 core 内部模块；skill_runtime 不依赖四个 Engine；Engine 之间禁止 import 实现；LangChain 仅在 Adapter/Integration；FastAPI 仅在 API/Adapter；bootstrap 是组合根。

## 7. 目标目录

```text
skills/builtin/{incident-analysis,hypothesis-generation,evidence-planning,
                reflection,reproduction-planning,rca-report}/

src/ops_agent/
  contracts/  ports/  core/
  skill_runtime/{manifest,loader,validator,registry,resolver}.py
  knowledge/  reasoning/  investigation/  reproduction/
  integrations/mcp/
  integrations/{codebuddy,codex,local_agent}/

tests/fixtures/product-skills/{test-product-v1,test-product-v2}/
```

真实资产位于外部 `product-skill-repository` 和 `tool-skill-repository`。

## 8. 所有权与演进

所有跨模块数据继续使用既有 Contract v1。Skill Manifest 是插件生命周期元数据，不替代业务 Contract。Knowledge Plugin 内容必须经 Engine 标准化后才能进入 Runtime。

Evidence Graph 权威状态仍归 Runtime；Investigation/Reproduction 只生产 Evidence。LLM/Agent 文本必须结构化校验后成为 TaskResult。当前保持模块化单体；未来拆服务只增加既有 Port 的远程 Adapter。

## 9. Baseline v0.2 验证

- 守护 Core/Knowledge 不依赖 product crawler、Playwright crawler 或 LangChain；
- 验证 Skill 发现、缺失错误、版本隔离和类型区分；
- 验证 PluginKnowledgeEngine 通过 KnowledgePort 查询合成测试插件；
- 原 Contract、Core、Knowledge、Fake E2E 和 Agent Host 测试继续通过。

本次对齐不重写四个 Engine、Runtime、Contract、Port 或 Fake E2E。
