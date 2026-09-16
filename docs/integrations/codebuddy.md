# CodeBuddy External Agent Adapter

> 状态：Mock verified / real CodeBuddy client pending  
> 日期：2026-09-15  
> 范围：Step 9，无状态 Reasoning Owner Adapter

## 1. 定位

CodeBuddy 只充当当前 RuntimeTask 的 Reasoning Owner。IncidentState、Stage、重试、超时、循环、审批和终止状态全部归 Core Runtime 所有。

```text
CodeBuddyAdapter
  -> incident_start
  -> incident_next
  -> RuntimeTaskSkillRouter
  -> CodeBuddy/Fake Reasoning Owner
  -> TaskResult
  -> incident_submit
  -> repeat until Runtime terminal state
```

Adapter 依赖 `RuntimePort`，因此可注入 `RuntimeMcpClient` 或未来 Runtime API Client。MVP 默认使用 Runtime MCP，模块之间没有改为 HTTP 调用。

## 2. 实现结构

- `CodeBuddyAdapter`：执行有界的 start/next/reason/submit 循环。
- `CodeBuddyAdapterConfig`：选择 `mcp` 或 `api` Runtime transport，并限制最大迭代次数。
- `RuntimeTaskSkillRouter`：显式映射 RuntimeStage 到 Step 8 Canonical Skill。
- `ReasoningOwner`：一次只接收 RuntimeTask、只读 IncidentState 快照和对应 Skill，返回 TaskResult。
- `FakeExternalAgent`：离线测试用 Reasoning Owner；自身没有 RuntimePort、Repository 或 submit 方法。
- `FakeTaskReasoner`：只调用 Fake Engine Port 完成一项任务，不接收 Runtime。

`CodeBuddyRunOutcome` 保存运行期间观察到的 Stage 和已加载 Skill，但权威状态仍是 Runtime 返回的 `final_state`。

## 3. 统一交互协议

1. 用 `incident_start` 提交 `StartIncidentRequest`。
2. 用 `incident_next` 获取唯一待处理 `RuntimeTask`。
3. 按任务 Stage 加载 Canonical Skill。
4. Reasoning Owner 只完成本轮任务，并产生 `TaskResult`。
5. 用 `incident_submit` 提交结果。
6. 重复 next/submit。
7. Runtime 返回 `COMPLETED` 后，从 `IncidentState.rca_report` 获取 RCA。

如果 Runtime 返回 `FAILED` 或 `WAITING_HUMAN`，Adapter 立即退出，不自行重试、批准或跳转。

## 4. Skill 映射

| Runtime Stage | Canonical Skill |
|---|---|
| `NORMALIZE` | `incident-analysis` |
| `KNOWLEDGE_LOOKUP` | `incident-analysis`；产品插件由 Knowledge Engine 解析 |
| `HYPOTHESIS` | `hypothesis-generation` |
| `EVIDENCE_PLAN` | `evidence-planning` |
| `INVESTIGATE` | `incident-analysis` |
| `ROOT_CAUSE_ASSESSMENT` | `incident-analysis` |
| `EXPERIMENT_PLAN` | `reproduction-planning` |
| `REPRODUCE` / `VERIFY` | `incident-analysis` |
| `REFLECT` | `reflection` |
| `RCA` | `rca-report` |

映射是方法论选择，不是状态转换表。只有 Runtime 能决定下一个 Stage。

## 5. 配置示例

Adapter 配置见 [adapter.example.toml](../../examples/integrations/codebuddy/adapter.example.toml)：

```toml
runtime_transport = "mcp"
skills_target = "codebuddy"
max_iterations = 50
```

MCP 配置模板见 [mcp.example.json](../../examples/integrations/codebuddy/mcp.example.json)。其中 `<runtime-mcp-server-command>` 和 `<tool-mcp-server-command>` 是有意保留的占位符：Step 7 尚未实现真实 stdio MCP Server，不应声称存在可启动命令。

## 6. Canonical Skill 安装

不要手工复制或修改六份 Built-in Method Skill。使用 Builder 从 `skills/builtin/` 构建 CodeBuddy target：

```python
from pathlib import Path

from ops_agent.skills import CanonicalSkillBuilder, SkillCatalog, SkillTarget

catalog = SkillCatalog(Path("skills/builtin"))
builder = CanonicalSkillBuilder()
for skill in catalog.load_all():
    builder.build(skill, target=SkillTarget.CODEBUDDY, destination=Path("build/skills"))
```

随后将 `build/skills/codebuddy/` 中的构建产物安装到真实 CodeBuddy 客户端所配置的 Skill 目录。该目录位置和发现格式必须以目标客户端版本为准；本步骤没有真实客户端，未假定一个未经验证的固定路径。

## 7. 启动方式

### 离线 Mock

仓库内的集成测试是当前可执行启动方式：

```bash
.venv/bin/pytest tests/integration/codebuddy
```

它使用 `RuntimeMcpClient -> runtime-mcp -> CoreRuntime` 和 Fake Engine，完整运行订单超时重试案例。

### 真实 CodeBuddy

1. 提供实际可运行的 Runtime MCP stdio/HTTP Server binding。
2. 将 MCP 配置模板中的 command 占位符替换为已验证命令。
3. 构建并安装 `codebuddy` target Skills。
4. 在隔离测试环境中使用示例 Prompt 启动会话。
5. 核对 CodeBuddy 的 Tool Schema、超时、错误和审批交互后，才能标记真实客户端验证完成。

当前步骤未实现第 1 项，因此不能声称真实启动已经可用。

## 8. Example Prompt

完整示例位于 [example-prompt.md](../../examples/integrations/codebuddy/example-prompt.md)。其核心约束是一次只处理一个 RuntimeTask，并明确禁止直接修改 IncidentState、绕过 Validator 写 Evidence 或一次性完成整个诊断。

## 9. 安全边界

CodeBuddy Adapter 不允许：

- 持有或写入 StateRepository；
- 自行构造下一 Stage；
- 不经 `incident_submit` 修改状态；
- 绕过 Runtime 接受未校验 Evidence；
- 因 Skill 声明了 MCP Tool 就绕过 Policy/Human Approval；
- 在 Runtime 终态后继续提交任务。

Runtime 会再次校验 task_id、incident_id、request_id、Stage、deadline 和 `TaskOutput`，所以 Agent 输出不是权威状态。

## 10. 验证状态与限制

已验证：

- 配置文件可解析并通过 `CodeBuddyAdapterConfig` 校验；
- MCP JSON 示例合法；
- Stage 到 Canonical Skill 的映射；
- FakeExternalAgent 严格执行 next → reason → submit；
- Runtime MCP E2E 到 `COMPLETED` 并产生 RCA；
- Fake Reasoning Owner 没有 Runtime start/submit 能力。

待验证：

- 真实 CodeBuddy Skill 安装目录和发现行为；
- 真实 CodeBuddy MCP 配置字段兼容性；
- 真实 stdio/HTTP MCP Server 启动；
- 在线模型的 TaskResult 结构化输出质量、超时和人工审批体验。

结论：Mock 验证通过，真实客户端待验证。
