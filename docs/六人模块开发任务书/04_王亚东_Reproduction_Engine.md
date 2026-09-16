# 王亚东 — Reproduction Engine 开发任务书

> 开发前先阅读根目录 `AGENTS.md` 与本文件。技术栈统一：Python 3.11+ / FastAPI / LangChain / Pydantic v2。

## 1. 模块定位

解决：**如何把高可信根因假设转成可执行实验，通过环境准备、故障注入和证据判定真正复现问题。**

核心能力：Environment Prepare/Reset、Playwright、API/Shell、故障注入、网络延迟/超时/抖动、k6、mitmproxy/Toxiproxy、Chaos Mesh、Experiment Execute、Verifier、Cleanup、最小复现、回归资产。

核心价值：**把推断变成实验，把实验结果变成可重复验证的证据。**

## 2. 代码边界

```text
src/ops_agent/reproduction/
skills/builtin/reproduction-planning/
src/ops_agent/integrations/mcp/reproduction/
tests/reproduction/
docs/modules/06-reproduction.md
```

## 3. 必须实现的接口

```python
ReproductionPort.prepare(...)
ReproductionPort.execute(...)
ReproductionPort.verify(...)
ReproductionPort.cleanup(...)
```

对应 Tool Ports：BrowserToolPort、ApiToolPort、ShellToolPort、FaultInjectionToolPort。Playwright、Toxiproxy、mitmproxy、k6、Chaos Mesh 均是 MCP/Adapter 工具，不是 Runtime 或 Planning Skill 实现。

目标：`FakeReproductionEngine -> RealReproductionEngine`。

## 4. 输入/输出

输入：`ExperimentPlan`、相关 `Hypothesis`、必要 `KnowledgeContext`、必要 `Evidence[]`。

输出：`EnvironmentResult`、`ExperimentResult`、`VerificationResult`、`CleanupResult`。

ExperimentResult 至少包含：experiment_id、hypothesis_id、environment、actions、start/end time、success/failure、collected evidence refs、actual behavior、expected behavior、verifier conclusion、cleanup status。

## 5. 第一阶段 MVP

固定 Case：首次创建请求实际成功，但人为延迟响应，客户端自动重试，最终形成重复创建。

第一阶段建议只做：

```text
Playwright
+
mitmproxy 或 Toxiproxy（二选一）
+
测试后端
+
测试数据库
```

必须支持：

1. setup：恢复测试初态；
2. prepare：准备账号/数据；
3. fault inject：仅延迟首次响应；
4. execute：Playwright 触发真实操作；
5. verify：两次请求、第一次成功、第二次再次创建、DB 两条结果；
6. cleanup：恢复环境；
7. 形成最小复现说明。

要求一键可重复执行，不能依赖人工改数据库。

## 6. 后续扩展

MVP 后再扩：k6、MQ 重复消费、Chaos Mesh、CPU/内存/连接池限制、时间/TTL、多版本配置、回归 Playwright Test/pytest、HTML/JUnit 报告。

## 7. 对接关系

| 对接模块 | 对方给你 | 你返回 | 联调要求 |
|---|---|---|---|
| Reasoning | ExperimentPlan | ExperimentResult | 不接受自由文本实验指令 |
| Investigation | 证据采集需求 | 实验期间证据引用 | 时间窗口与 Experiment 对齐 |
| Knowledge | 版本能力/前置条件 | 复现结果 | 实验遵守版本条件 |
| Runtime | 执行状态/超时/审批 | 标准 Result | Runtime 不写死工具步骤；高风险写操作必须可拦截 |
| Integration | E2E 测试 | Reproduction MCP | 外部 Agent 不得绕 Runtime 直接注入 |

## 8. 测试要求

至少覆盖：正常实验、故障注入失败、Playwright 失败、验证失败、Cleanup 始终执行、重复 Cleanup 安全、超时、环境未准备、Experiment/Hypothesis ID 对应、Result Contract 合法。

建议：

```text
tests/reproduction/test_prepare.py
tests/reproduction/test_execute.py
tests/reproduction/test_verify.py
tests/reproduction/test_cleanup.py
tests/reproduction/test_timeout_delay_case.py
tests/reproduction/test_cleanup_on_failure.py
tests/reproduction/test_real_reproduction_port_contract.py
```

## 9. 独立验收

先组合：`FakeKnowledge + FakeReasoning + FakeInvestigation + RealReproduction`，Fake E2E 不回退；再跑真实 MVP Case。

```bash
pytest tests/reproduction -q
pytest tests/contracts -q
pytest tests/e2e/test_fake_incident_flow.py -q
ruff check .
mypy src
```

真实 MVP 必须提供一键 `setup -> run -> verify -> cleanup`。

## 10. 交付物

RealReproductionEngine、Playwright Adapter、故障注入 Adapter、Reproduction MCP、测试后端/环境说明、Verifier、Cleanup、最小复现 Case、测试、模块文档、实际验证记录。

最终验收：**给定标准 ExperimentPlan，可自动准备、执行、验证、清理；替换 Fake 后其他模块无需修改。**
