# 赵瑞琴 — Integration / Agent Host / Eval 开发任务书

> 开发前先阅读根目录 `AGENTS.md` 与本文件。技术栈统一：Python 3.11+ / FastAPI / LangChain / Pydantic v2。

## 1. 模块定位

负责证明：**同一套 Skill + MCP + Runtime，可以被不同 Agent Host 使用，并产出兼容的标准 Contract。**

主要内容：CodeBuddy Client/CLI、Codex Client/CLI、Local Agent、Agent Adapter、LLM Provider、MCP 配置、Canonical Skill Packaging、Agent Host Skill Adaptation、E2E、CI、Eval Case、Demo Harness。

注意：**不开发自己的 CLI。** CodeBuddy CLI/Codex CLI 指使用现有 CLI。

## 2. 代码边界

```text
src/ops_agent/integrations/
src/ops_agent/integrations/mcp/runtime/
src/ops_agent/skills/
tests/integration/
tests/e2e/
eval/
docs/integrations/
```

## 3. External Agent Host

需要让现有 Host 使用核心能力：CodeBuddy Client、CodeBuddy CLI、Codex Client、Codex CLI。

统一协议：

```text
incident_start
→ incident_next
→ 读取 RuntimeTask
→ 使用对应 Skill 推理
→ incident_submit
→ 循环
→ COMPLETED
→ RCAReport
```

External Agent 不允许：修改 IncidentState、自己跳状态、绕 Runtime 完整诊断、绕 Validator 写 Evidence、绕 Runtime 执行高风险实验。

## 4. Local Small Model Agent

建议结构：

```text
Local Agent
└─ LangChain Adapter
   └─ LLMProviderPort
      ├─ FakeLLMProvider
      └─ OpenAICompatibleProvider
```

目标兼容 vLLM、Qwen、GLM、其他 OpenAI-Compatible API，不硬编码具体模型。

每次模型只处理单个 RuntimeTask，输出必须经过：`Structured Output → Validator → Retry → Fallback → submit_task_result`。

## 5. 对接关系

| 对接模块 | 你需要 | 你提供 |
|---|---|---|
| Runtime | RuntimePort / Runtime MCP | Agent Host 协议验证 |
| Knowledge | 已安装 Product/Troubleshooting Plugin 的标准输出 | Host 适配验证，不读取插件内部文件 |
| Reasoning | Structured Reasoning Schema | Local Agent LLM Provider |
| Investigation | Observability MCP | MCP 集成验证 |
| Reproduction | Reproduction MCP | 高风险工具边界验证 |

## 6. 第一阶段 MVP

先证明两种 Host：

A. `FakeExternalAgent` 完整跑通 Fake E2E。

B. `Local Agent + FakeLLMProvider` 跑通同一 Case。

若真实 CodeBuddy 环境可用，再增加 C. `CodeBuddy CLI`，加载同一 Skill + Runtime MCP 跑同一 Case。

比较：最终 Contract、Runtime 路径、Evidence ID 合法性、Agent 是否绕过 Runtime。

还需验证：同一 Built-in Skill、同一已安装 Product Plugin、同一 Runtime MCP 可被 CodeBuddy Client/CLI、Codex Client/CLI 和 Local Agent 使用；平台差异只能存在于 packaging/adapter，不能复制业务方法论。

## 7. 评测集

维护 `eval/cases/`，至少包括：

1. timeout_retry_duplicate_create
2. missing_information
3. evidence_source_unavailable
4. reproduce_failed_then_reflect
5. unsupported_version

每个 Case 定义 input、expected stage path、expected evidence types、expected root-cause class、required constraints、forbidden behavior。不要只按最终文本相似度评分。

## 8. 测试要求

至少：

```text
tests/integration/test_runtime_mcp.py
tests/integration/test_external_agent_protocol.py
tests/integration/test_local_agent_fake_llm.py
tests/integration/test_invalid_task_result.py
tests/integration/test_agent_cannot_mutate_state.py
tests/integration/test_agent_resume.py
tests/integration/test_skill_mcp_reference.py

tests/e2e/test_fake_incident_flow.py
tests/e2e/test_local_agent_flow.py
tests/e2e/test_agent_host_contract_equivalence.py
```

验证：Agent 中断恢复、非法 TaskResult 拒绝、不存在 Evidence ID 拒绝、Local Agent 非法 JSON Retry/Fallback、Skill 引用 MCP Tool 存在、不同 Host 最终 Contract 一致。

## 9. 独立验收

```bash
pytest tests/integration -q
pytest tests/e2e -q
pytest tests/contracts -q
ruff check .
mypy src
```

真实 CodeBuddy/Codex 未验证时必须明确写：`Fake/Protocol 验证通过，真实 Host 待验证`。

## 10. 交付物

CodeBuddy/Codex Client/CLI 配置和说明、Local Agent、Provider、Runtime MCP、Canonical Skill Packaging、Agent Host Skill Adaptation、Product Plugin 加载兼容验证、Eval、E2E、CI 和验证记录。

最终验收：**至少两种不同 Agent Host 能使用同一套 Skill + MCP + Runtime 跑同一 Case，并输出兼容的标准 Contract。**
