# CodeBuddy Integration & Verification

> Ops Agent `0.1.0` · CodeBuddy External Reasoning Owner · 2026-09-16
> 状态：Plugin/Skill/Streamable HTTP MCP 协议验证完成；真实 CodeBuddy Host 待验证。

本文遵循 CodeBuddy 官方的 [Plugin Reference](https://www.codebuddy.ai/docs/cli/plugins-reference)、
[CLI Reference](https://www.codebuddy.ai/docs/cli/cli-reference) 和
[MCP configuration](https://www.codebuddy.ai/docs/cli/mcp)。

## 1. 集成边界

CodeBuddy 只负责当前 `RuntimeTask` 的推理，加载 Built-in Method Skill，生成结构化 `TaskResult` 并
调用 Runtime MCP。IncidentState、状态转换、重试、超时、循环、审批和终态全部由 Core Runtime 管理。

CodeBuddy 不安装或读取 Product/Troubleshooting Plugin，不配置 Product Skill Path，不运行 Crawler
Tool Skill，也不直接连接 Observability/Reproduction MCP。

```text
CodeBuddy -> Built-in Skills -> Runtime MCP -> Core Runtime
                                           -> Engine/Adapter

Server Product Repository -> Skill Runtime -> Knowledge Engine
```

## 2. 前置条件

- Ops Agent Core `0.1.0`；
- Docker Engine + Compose，或可直接运行 Python 3.11 应用；
- CodeBuddy Code CLI/Client 已安装、登录，且版本支持 Plugin 与 HTTP MCP；
- Server 侧已安装目标 Product/Troubleshooting Plugin；
- CodeBuddy 主机能够访问 Ops Agent 的 `8000/tcp`；
- 非本机访问时配置 TLS/网关和 `OPS_AGENT_MCP_ALLOWED_HOSTS`。

本仓库当前环境没有 `codebuddy` 命令，不能把以下官方命令写成已实测结果。

## 3. 启动 Ops Agent Core

TestProduct 仅用于隔离验收：

```bash
OPS_AGENT_PRODUCT_SKILLS_HOST_PATH="$PWD/tests/fixtures/product-skills" \
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

生产环境把 Host 路径改为外部 Product Skill Repository，不要挂载测试 fixture。

## 4. Product Skill 安装

Product 和 Troubleshooting Skill 只安装到 Server：

```text
Host Product Skill Repository
  -> /opt/ops-agent/plugins/product-skills:ro
  -> Skill Runtime
  -> RealKnowledgeEngine
```

安装和预检查见 [Skill Installation](../deployment/01-skill-installation.md)。真实 V7R2 Skill 不得复制
到 CodeBuddy Plugin。

## 5. Plugin 目录

```text
integrations/codebuddy/ops-agent-plugin/
├── .codebuddy-plugin/plugin.json
├── .mcp.json
├── README.md
└── skills/
    ├── incident-analysis/SKILL.md
    ├── hypothesis-generation/SKILL.md
    ├── evidence-planning/SKILL.md
    ├── reflection/SKILL.md
    ├── reproduction-planning/SKILL.md
    └── rca-report/SKILL.md
```

Plugin Skill 是 `skills/builtin/` 的生成制品，不是第二份手工业务源。生成或校验：

```bash
.venv/bin/python scripts/build_codebuddy_plugin.py
.venv/bin/python scripts/build_codebuddy_plugin.py --check
```

禁止直接编辑 Plugin 下的 `SKILL.md`。

## 6. 本地开发加载

CodeBuddy 官方开发参数是：

```bash
codebuddy --plugin-dir ./integrations/codebuddy/ops-agent-plugin
```

编辑 canonical Skill 并重新构建后，在交互会话执行 `/reload-plugins`。Skill 使用 Plugin namespace，
例如 `/ops-agent:incident-analysis`；用 `/help` 检查六个 Skill。

## 7. 正式安装与卸载

正式安装需要先把目录发布到企业 CodeBuddy Marketplace。发布后使用真实 marketplace 名称：

```bash
codebuddy plugin install ops-agent@<internal-marketplace> --scope user
codebuddy plugin enable ops-agent@<internal-marketplace> --scope user
codebuddy plugin uninstall ops-agent@<internal-marketplace> --scope user
```

当前仓库没有发布 Marketplace，因此 `<internal-marketplace>` 是部署方必须替换的发布标识，不是可执行
默认值。开发验证优先使用 `--plugin-dir`，不会修改用户全局 Plugin 配置。

## 8. MCP 配置与 Endpoint

实际 transport 是 MCP **Streamable HTTP**：

```text
http://127.0.0.1:8000/mcp/runtime/
```

Plugin `.mcp.json` 只定义 `ops-agent-runtime`，URL 来自非敏感 `userConfig.runtime_endpoint`。当前 Core
没有认证，所以没有 `runtime_token`，不得虚构 Token。远程部署必须在反向代理层增加 TLS、认证和授权。

开发时若要排除用户其他 MCP 干扰，使用显式配置：

```bash
codebuddy \
  --plugin-dir ./integrations/codebuddy/ops-agent-plugin \
  --mcp-config ./integrations/codebuddy/runtime-mcp.example.json \
  --strict-mcp-config
```

`--strict-mcp-config` 会忽略 Plugin/user/project MCP，因此上面同时显式传入只含 Runtime MCP 的配置。

非本机 endpoint 还必须在 Server 配置精确 Host：

```dotenv
OPS_AGENT_MCP_ALLOWED_HOSTS=ops-agent.internal.example:8000
```

## 9. CodeBuddy Client 使用

在 CodeBuddy Client 的本地 Plugin 开发入口选择
`integrations/codebuddy/ops-agent-plugin/`，按提示填写 `runtime_endpoint`。确认 Plugin namespace 为
`ops-agent`，且 MCP 面板只出现 `ops-agent-runtime`。

不同 Client 发行版的 GUI 菜单可能不同，必须以所安装版本界面为准；本仓库没有真实 Client 可验证。

## 10. CodeBuddy CLI 使用

交互模式：

```bash
codebuddy --plugin-dir ./integrations/codebuddy/ops-agent-plugin --debug
```

隔离打印模式：

```bash
codebuddy \
  --plugin-dir ./integrations/codebuddy/ops-agent-plugin \
  --mcp-config ./integrations/codebuddy/runtime-mcp.example.json \
  --strict-mcp-config \
  -p "$(cat examples/integrations/codebuddy/example-prompt.md)"
```

不要使用 `--dangerously-skip-permissions` 作为验收前提。

## 11. 确认 Skill 已加载

1. 使用 `--debug` 查找 Plugin load/validation 日志；
2. 在交互模式运行 `/help`；
3. 确认 `/ops-agent:incident-analysis`、`hypothesis-generation`、`evidence-planning`、
   `reflection`、`reproduction-planning`、`rca-report`；
4. 修改后运行 `/reload-plugins`。

## 12. 确认 Runtime MCP 已连接

用 `--debug` 或 CodeBuddy MCP 状态界面确认 `ops-agent-runtime` 已连接，并且只出现：

- `incident_start`
- `incident_next`
- `incident_submit`
- `incident_get_state`
- `incident_finish`

服务端可用官方 Python MCP Client 做独立诊断；普通 `curl GET` 不是完整 MCP 握手。

## 13. 第一个 Incident

建议输入：

```text
使用 /ops-agent:incident-analysis 分析以下问题：
产品：TestProduct
版本：1.0
问题：创建订单时第一次响应超时，客户端重试后产生重复创建。

必须从 incident_start 开始，每次只处理 incident_next 返回的一项 RuntimeTask，
用结构化 TaskResult 调用 incident_submit；禁止直接修改 IncidentState。
```

预期顺序是 `incident_start -> incident_next -> incident_get_state -> load stage Skill ->
incident_submit -> repeat -> incident_finish/RCAReport`。

## 14. 查看完整流程和 RCA

每次提交后调用 `incident_get_state`，记录 Incident ID、`runtime_stage`、revision、pending task 和 audit
correlation。只有 `runtime_stage=COMPLETED` 才视为完成；最终从 `IncidentState.rca_report` 或
`incident_finish` 获取 RCAReport。

RCA 必须区分 confirmed facts、inferences、root causes、remediation、unverified items 和 evidence chain。

## 15. 配置清单

| 配置项 | 必需 | 配置位置 | 示例 | 敏感 | 验证 |
|---|---:|---|---|---:|---|
| CodeBuddy Plugin Path | 开发态是 | CLI `--plugin-dir` | `./integrations/codebuddy/ops-agent-plugin` | 否 | `/help` |
| Runtime MCP Endpoint | 是 | Plugin userConfig 或 `--mcp-config` | `http://127.0.0.1:8000/mcp/runtime/` | 否 | 五个 Tool 可见 |
| MCP Transport | 是 | Plugin `.mcp.json` | `http` | 否 | Debug 显示 connected |
| Product | 每次 Incident 是 | 用户 ProblemContext | `TestProduct` | 否 | ProductContext 精确匹配 |
| Version | 每次 Incident 是 | 用户 ProblemContext | `1.0` | 否 | 不回退其他版本 |
| Runtime Token | 否/不存在 | 无 | 无 | — | 当前 Core 无认证 |
| Skill enabled | 是 | Plugin enable/当前 session | `ops-agent` | 否 | `/help` |
| MCP enabled | 是 | Plugin 或显式 MCP config | `ops-agent-runtime` | 否 | MCP 状态/工具列表 |
| Product Skill Path | CodeBuddy 禁止 | Server `.env`/volume | Server only | 受控资产 | Server preflight |
| Crawler Tool Skill | 禁止 | 外部知识生产环境 | 不配置 | — | Plugin 中不存在 |

## 16. 错误版本与边界验证

提交不存在版本时，Knowledge Engine 应返回明确的版本未安装错误，不允许选取其他版本。检查 CodeBuddy
Plugin 目录没有 `skill.toml`、Product payload 或 TestProduct 内容；Product 文件只能出现在 Server
volume。

## 17. Runtime MCP 不可用和恢复

执行 `docker compose stop ops-agent` 后，CodeBuddy 应明确报告 `ops-agent-runtime` 不可连接，不得输出
已完成 RCA。执行 `docker compose start ops-agent` 恢复服务。

当前 StateRepository 是内存实现，服务重启后 Incident **不能恢复**。必须重新 `incident_start`；持久化
恢复是后续能力，不得标记为已验证。

## 18. Debug 与常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| Plugin 不出现 | 目录或 manifest 错误 | `codebuddy --debug --plugin-dir ...`；检查 manifest |
| Skill 不出现 | 生成制品过期 | 运行 builder 与 `--check`，然后 `/reload-plugins` |
| MCP 无工具 | endpoint/配置错误 | 检查 `.mcp.json` 和 `/mcp/runtime/` 尾部斜杠 |
| MCP 返回 421 | Host 不在 allowlist | 更新 `OPS_AGENT_MCP_ALLOWED_HOSTS` 并重启 |
| Product/version 不存在 | Server 插件未安装 | Server 跑 preflight，不在 CodeBuddy 安装 Product Skill |
| 服务恢复后 Incident 丢失 | InMemory repository | 重新开始；不能伪造恢复 |
| 高风险工具不可见 | Plugin 只连接 Runtime MCP | 这是预期安全边界 |

## 19. 升级

1. 更新 canonical `skills/builtin/`；
2. 增加 Plugin SemVer；
3. 运行 builder 和 `--check`；
4. 运行 Plugin/MCP/E2E/静态检查；
5. 开发态 `/reload-plugins`；正式环境发布新 Marketplace 版本；
6. 不把 Product Skill 随 Plugin 发布。

## 20. 当前端到端限制

Runtime MCP transport 和五个工具已经可连接，但当前 `CoreRuntime.get_next_task()` 只生成
`payload={"stage": ...}`，不会在 Server 侧自动调用 Knowledge/Investigation/Reproduction Engine。现有
Fake E2E 由 Python `FakeTaskReasoner` 持有 Engine Ports 执行任务。

因此，“CodeBuddy 只连接 Runtime MCP，同时 Product Skill 只在 Server，并完整完成 TestProduct RCA”在
当前公共接口下仍缺少一个 **Server-side Task Execution/Application Service** 边界。不能让 CodeBuddy
读取 Product 文件，也不能让 MCP transport 偷偷实现 Engine 编排。此项需要单独的 Interface Change
Proposal 后才能真实闭环，本步骤没有修改 Runtime 状态机或把业务编排塞进 MCP。
