# Local Agent / Small Model Agent

> 状态：Fake E2E verified / real OpenAI-compatible endpoint pending  
> 日期：2026-09-15  
> 范围：Step 11，本地小参数模型 Reasoning Owner 骨架

## 1. 定位与边界

Local Agent 是可替换的 Reasoning Owner，不是新的工作流引擎。Core Runtime、状态转换表、IncidentState、重试/超时、人工审批与停止条件均保持不变。

```text
LocalAgentRunner
  -> RuntimePort: start / next / get_state
  -> RuntimeTaskSkillRouter: 加载本任务 Canonical Skill
  -> LocalSmallModelAgent
       -> LLMProviderPort
       -> StructuredTaskOutputValidator
       -> Retry
       -> deterministic Fallback（可选）
  -> RuntimePort: submit
  -> repeat until Runtime terminal state
```

Runner 只能使用 RuntimePort 读取任务和提交 TaskResult，不持有 StateRepository，也不能直接修改 IncidentState 或决定下一 Stage。

## 2. 模块结构

| 组件 | 职责 |
|---|---|
| `LLMProviderPort` | Provider 无关的异步接口；输入/输出只使用 Pydantic Contract |
| `FakeLLMProvider` | 离线、确定性地产生结构化 JSON，用于完整 Fake E2E |
| `OpenAICompatibleProvider` | integrations 边界内的 LangChain `ChatOpenAI` Adapter |
| `LocalSmallModelAgent` | 对一个 RuntimeTask 执行校验、重试和 fallback |
| `StructuredTaskOutputValidator` | 将原始 JSON 转成 TaskOutput，并校验阶段、枚举、数量和引用 |
| `LocalAgentRunner` | 执行 start → next → reason → submit 有界循环 |
| `RuntimeTaskSkillRouter` | 与 External Agent 共用的 Runtime Stage → Canonical Skill 映射 |

LangChain 仅存在于 `integrations/local_agent/providers.py`。`contracts`、`ports`、`core`、各 Engine domain 均不依赖 LangChain 或任何模型厂商 SDK。

## 3. 一次只处理一个 RuntimeTask

每次 Provider 调用只包含当前 RuntimeTask、当前 Skill、要求填充的唯一 TaskOutput 字段、JSON Schema，以及按 Stage 裁剪后的状态摘要：

| Stage | 模型任务与可见上下文 |
|---|---|
| `NORMALIZE` | 规范化 ProblemContext |
| `KNOWLEDGE_LOOKUP` | 根据 ProblemContext 形成知识查询结果 |
| `HYPOTHESIS` | 根据产品、知识、排障上下文和已有证据生成有限候选 |
| `EVIDENCE_PLAN` | 仅基于 Hypothesis 和已有 Evidence 选择允许的 EvidenceType |
| `INVESTIGATE` | 仅完成当前 EvidencePlan 对应的结构化证据批次 |
| `ROOT_CAUSE_ASSESSMENT` | 仅根据已有 Hypothesis、Evidence、Verification 评估根因 |
| `EXPERIMENT_PLAN` | 将目标 Hypothesis 转为有界且可回滚的 ExperimentPlan |
| `REPRODUCE` | 仅返回当前实验的 ExperimentResult |
| `VERIFY` | 仅验证已执行实验，不创建新现场事实 |
| `REFLECT` | 仅分析失败/不足并建议下一动作，不执行状态跳转 |
| `RCA` | 只根据已有事实和证据链生成结构化 RCAReport |

模型不会收到“诊断整个 Incident”的开放式请求。Runtime 每次只接受与当前 Stage 对应的一个 typed output。

## 4. Structured Output 安全链

固定处理链如下：

1. Provider 返回 `LLMResponse.content` 原始 JSON 字符串。
2. Pydantic v2 以 `TaskOutput.model_validate_json` 解析，拒绝非法 JSON、缺失字段、未知字段和错误枚举。
3. Validator 确认只填充当前 Stage 要求的 TaskOutput 字段。
4. Validator 限制 Hypothesis 数量和 EvidenceType 允许集合。
5. Validator 检查 Hypothesis/Evidence 等引用必须已存在于 Runtime 提供的状态快照。
6. 成功后才构造 `TaskResult.typed_output`；原始自由文本不会提交 Runtime。
7. 失败时在 `max_validation_attempts` 范围内重新请求；全部失败后调用显式 fallback。没有 fallback 时提交机器可读的失败 TaskResult，由 Runtime 负责错误路由。

重试不会绕过 Validator，fallback 也必须返回合法 TaskResult。默认最多尝试 2 次，可配置范围为 1–10。

## 5. Provider 配置

`OpenAICompatibleProviderConfig` 不提供默认模型，部署方必须注入模型名、地址和凭据：

```python
from ops_agent.integrations.local_agent import (
    OpenAICompatibleProvider,
    OpenAICompatibleProviderConfig,
)

provider = OpenAICompatibleProvider(
    OpenAICompatibleProviderConfig(
        model="deployment-selected-model",
        base_url="http://127.0.0.1:8000/v1",
        api_key="replace-at-runtime",
        temperature=0.0,
        timeout_seconds=30,
        json_mode=True,
    )
)
```

凡提供 OpenAI-compatible Chat Completions 接口的 vLLM、Qwen 或 GLM 部署均可通过相同配置接入；具体模型名、URL、鉴权、上下文窗口和服务启动参数属于部署配置，不在代码中硬编码。密钥应由环境或 Secret 管理系统注入，不能提交仓库。

测试可注入任意 LangChain `BaseChatModel`，因此 Provider contract test 不需要联网。

## 6. Fake E2E

`FakeLLMProvider` 把 Step 5 的确定性 Engine Port 结果序列化成与真实模型相同的 JSON 边界。它仍经过同一个 StructuredTaskOutputValidator，不能绕开验证。完整测试路径为：

```text
LocalAgentRunner
  -> RuntimeMcpClient
  -> runtime-mcp
  -> CoreRuntime
  -> RuntimeTask
  -> FakeLLMProvider + Fake Engines
  -> Validator
  -> TaskResult
  -> CoreRuntime
  -> COMPLETED + RCAReport
```

测试没有人工修改 IncidentState。

## 7. 失败策略

- 非法 JSON、字段缺失、错误枚举：验证失败并重试。
- 虚构 Evidence ID、未知 Hypothesis ID：引用完整性失败并重试。
- Hypothesis 超出配置数量、EvidenceType 不在 allow-list：策略校验失败并重试。
- Provider 异常：使用同一有界次数重试，避免无限循环。
- 重试耗尽且存在 fallback：调用确定性 Reasoning Owner。
- 重试耗尽且无 fallback：返回 `LOCAL_AGENT_OUTPUT_INVALID` 失败 TaskResult；是否重试、失败或等待人工由 Runtime 决定。
- Runtime 返回 `WAITING_HUMAN`、`FAILED` 或 `COMPLETED`：Runner 立即停止，不自行批准或继续提交。

## 8. 当前验证范围与限制

已验证：

- `LLMProviderPort` 不暴露 LangChain 类型；
- 注入 LangChain Fake ChatModel 的 OpenAI-compatible Adapter contract；
- 非法 JSON、字段缺失、错误枚举；
- 虚构 Evidence ID、Hypothesis 数量上限；
- Validator 重试和确定性 fallback；
- FakeLLMProvider 经 Runtime MCP 驱动订单重复创建案例到 `COMPLETED` 和 RCAReport；
- 全量 pytest、ruff、mypy 回归。

未验证：

- 真实 vLLM/Qwen/GLM/OpenAI-compatible 服务的网络、鉴权和 JSON mode 差异；
- 不同小模型的上下文窗口、吞吐、超时和结构化输出质量；
- 生产级 Secret 管理、限流、遥测和内容安全策略；
- fallback 的生产实现和人工审批体验。

在完成真实端点 contract suite 与隔离环境验证前，本模块应标记为“Fake/Mock 可用，真实模型待验证”。
