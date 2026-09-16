# CodeBuddy Verification Record

> 验证日期：2026-09-16  
> 结论：CodeBuddy 配置与协议验证完成，真实 Host 待验证。

## 版本与对象

| 项目 | 值 |
|---|---|
| CodeBuddy | 本机未安装，版本不可用 |
| Ops Agent | `0.1.0` |
| Docker image | `ops-agent-core:0.1.0` |
| MCP SDK | `mcp 2.2.0` |
| MCP transport | Streamable HTTP |
| Runtime endpoint | `http://127.0.0.1:18002/mcp/runtime/`（验收临时端口） |
| Product Skill | Synthetic TestProduct `1.0` + comparison `2.0` |
| Test Case | timeout + retry -> duplicate create |

正式默认 endpoint 是 `http://127.0.0.1:8000/mcp/runtime/`。本机已有其他容器占用 8000，因此验收使用
`OPS_AGENT_PORT=18002`，未停止或修改其他项目容器。

## Plugin 与 Skills

Plugin：`integrations/codebuddy/ops-agent-plugin/`

生成并校验的 Skill：

- incident-analysis
- hypothesis-generation
- evidence-planning
- reflection
- reproduction-planning
- rca-report

Plugin 只包含 Runtime MCP 配置；未包含 Product Skill、Troubleshooting payload、TestProduct 或 Crawler。

## MCP Tools

官方 Python MCP Client 通过容器 endpoint 实际发现：

```text
incident_start
incident_next
incident_submit
incident_get_state
incident_finish
```

`incident_start` 实际创建：

```text
Incident ID: INC-CODEBUDDY-VERIFY
initial stage: created
```

## 实际命令摘要

```bash
.venv/bin/python scripts/build_codebuddy_plugin.py --check

OPS_AGENT_PORT=18002 \
OPS_AGENT_MCP_ALLOWED_HOSTS=127.0.0.1:18002,localhost:18002 \
OPS_AGENT_PRODUCT_SKILLS_HOST_PATH="$PWD/tests/fixtures/product-skills" \
docker compose up -d --build

docker compose ps
curl --fail http://127.0.0.1:18002/health
curl --fail http://127.0.0.1:18002/ready

docker compose exec -T ops-agent \
  python /opt/ops-agent/scripts/verify_skill_installation.py \
  --product TestProduct --version 1.0 --comparison-version 2.0
```

结果：镜像构建成功；容器 healthy；health/ready 成功；Skill preflight `ok=true`；MCP 握手和 Tool list
成功。

错误版本也通过运行中容器的 Knowledge HTTP 边界进行了实际验证。查询 `TestProduct 9.9` 返回 HTTP
`503` 和终止型错误 `KNOWLEDGE_PRODUCT_VERSION_NOT_INSTALLED`，并明确报告仅安装了 `1.0`、`2.0`；
系统没有使用其他版本冒充目标版本。

## 不可用与恢复验证

停止 `ops-agent` 后，官方 MCP Client 连接失败并报告 `ExceptionGroup`，没有得到伪造结果。重新启动后
health/ready 和 MCP 恢复。

重启前创建的 `INC-CODEBUDDY-VERIFY` 在重启后读取失败，符合当前
`InMemoryStateRepository` 的非持久化边界；Incident 恢复未实现。

## RCA 与完整 Incident 状态

真实 CodeBuddy CLI/Client 未安装，因此没有真实 Host 产生的完整 Incident/RCA。现有
CodeBuddy Mock E2E、Fake E2E 和 Real Knowledge E2E 继续作为协议回归证据。

此外，当前 RuntimeTask 不携带 Engine 输出，Server 也没有自动 Engine Task Executor。只连接 Runtime
MCP 的真实 CodeBuddy 无法在不读取 Server Product Plugin 的前提下完成 Knowledge Task。该架构缺口已
记录在 `docs/integrations/codebuddy.md`，需要 Interface Change Proposal；本步骤没有把 Engine 编排放进
MCP transport。

## 成功/失败矩阵

| 验证项 | 结果 |
|---|---|
| Plugin 目录和 manifest 静态验证 | 成功 |
| 六个 Skill 与 canonical source 一致 | 成功 |
| Plugin 不含 Product/Tool Skill | 成功 |
| Docker build/up/health/ready | 成功（临时端口 18002） |
| TestProduct Server-side preflight | 成功 |
| HTTP MCP 握手和五个 Tool | 成功 |
| `incident_start` 实际调用 | 成功 |
| 不存在的 Product 版本返回明确错误 | 成功 |
| Server 停止时 MCP 明确不可用 | 成功 |
| Server 重启后 transport 恢复 | 成功 |
| Incident 重启恢复 | 不支持 |
| 真实 CodeBuddy Plugin 加载 | 未验证：CLI/Client 不存在 |
| 真实 CodeBuddy 最小 Incident/RCA | 未验证：Host 不存在且缺 Server-side Task Executor |
