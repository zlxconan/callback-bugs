# Ops Agent

Ops Agent 是一个 **Agent-independent 的智能问题分析与复现核心平台**。它不是把所有产品知识、工具和流程塞进一个智能体，而是用稳定 Contract、确定性 Runtime、可替换 Agent Host 和插件化能力组合线上问题分析。

Architecture Baseline v0.2 的核心组成：

- Contracts + Ports：跨模块公共语言与依赖倒置边界；
- Core Runtime：唯一 Incident 工作流、状态和策略所有者；
- Built-in Method Skills：与产品无关的分析方法论；
- Generic Skill Runtime：Skill Registry、Loader、Manifest、Resolver、Validator；
- Knowledge / Reasoning / Investigation / Reproduction 四个 Engine；
- Runtime、Observability、Code、Reproduction MCP 接口；
- CodeBuddy、Codex、Local Agent 等可替换 Agent Host。

外围能力不内置进 Core：

- Product Skill Plugin / Troubleshooting Skill Plugin 从外部 Product Skill Repository 安装；
- Observability MCP 与 Reproduction MCP 按部署环境和工具插件化；
- crawler、parser、PDF/website-to-skill 等 Tool Skill 属于独立知识生产链，不是 Incident Runtime 依赖。

```text
Agent Host -> Built-in Method Skill -> Runtime MCP -> Core Runtime
                                                |-> Knowledge -> Skill Runtime -> Product Plugins
                                                |-> Reasoning
                                                |-> Investigation -> Observability MCP
                                                `-> Reproduction -> Reproduction MCP

Product Website -> Crawler Tool Skill -> Playwright MCP
                -> Product Skill Package -> Product Skill Repository
```

## Skill 布局

```text
skills/builtin/                    # Core 随包发布的六个方法 Skill
tests/fixtures/product-skills/     # 仅用于测试的合成 Product Plugin
```

真实产品 Skill 和 Tool Skill 不进入本仓库。边界审计见 [Architecture Boundary Audit](docs/architecture/05-skill-boundary-audit.md)。

## 开发环境

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e '.[dev]'
```

## 启动与验证

```bash
uvicorn ops_agent.api.app:app --reload
ruff check .
ruff format --check .
mypy
pytest
```

健康端点：`GET /health`、`GET /ready`。

## Skill 部署前配置

开发环境可复制 `.env.example`。Real Knowledge 装配要求设置
`OPS_AGENT_PRODUCT_SKILLS_PATH`；Built-in 默认从仓库相对路径
`skills/builtin` 读取，容器部署时应显式设为 `/opt/ops-agent/skills/builtin`。

使用合成 TestProduct 做只读安装预检查：

```bash
set -a
source .env.example
set +a
.venv/bin/python scripts/verify_skill_installation.py \
  --product TestProduct --version 1.0 --comparison-version 2.0
```

真实 Product/Troubleshooting Skill 来自外部 Repository，不提交到本仓库。完整安装、升级、卸载和 volume mount 规则见
[Skill Installation](docs/deployment/01-skill-installation.md)。

架构基线见 [00-architecture-plan.md](docs/architecture/00-architecture-plan.md)。
