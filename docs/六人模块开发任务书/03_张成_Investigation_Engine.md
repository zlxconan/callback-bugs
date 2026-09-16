# 张成 — Investigation Engine 开发任务书

> 开发前先阅读根目录 `AGENTS.md` 与本文件。技术栈统一：Python 3.11+ / FastAPI / LangChain / Pydantic v2。

## 1. 模块定位

解决：**针对当前根因假设，下一步最需要什么真实证据，以及如何把外部可观测数据转成统一 Evidence。**

核心原则：Reasoning 决定“需要什么证据”；Investigation 通过 Tool Port/Observability MCP 负责“怎么拿到并标准化证据”。Reasoning 不直接调用各观测 MCP。

核心能力：Trace、Logs、Metrics、K8s Events/State、Change History、Service Graph/Topology、Evidence 标准化、Evidence Graph 数据输入、Batch Collect、Error/Timeout/Retry 适配。

特别保留：**Trace 优先于静态 Service Graph；Service Graph 是调查导航地图，不是固定日志遍历路径。**

## 2. 代码边界

```text
src/ops_agent/investigation/
src/ops_agent/integrations/mcp/observability/
tests/investigation/
docs/modules/05-investigation.md
```

## 3. 必须实现的接口

```python
InvestigationPort.collect(...)
InvestigationPort.collect_batch(...)
```

并实现相应 Tool Port Adapter：TraceToolPort、LogToolPort、MetricToolPort、K8sToolPort、ChangeToolPort、TopologyToolPort。

目标：`FakeInvestigationEngine -> RealInvestigationEngine`。

## 4. 输入/输出

输入：`EvidenceRequest`、`EvidencePlan`、只读 Incident 上下文。

输出：`Evidence` / `Evidence[]`。

每条 Evidence 至少包含：evidence_id、evidence_type、source、raw_ref、structured_value、timestamp、supports、contradicts、collection_status、confidence、error（如有）。

Investigation 不负责决定最终根因。

## 5. 第一阶段 MVP

统一 Case 只接最小三种证据：

1. HTTP Request/Response 记录
2. 应用日志
3. 数据库记录

第一阶段暂不要求 Prometheus、K8s、完整 Trace、Change History，但接口必须预留。

MVP 要证明：

- 同一业务标识存在两次请求；
- 第一次请求后端实际已成功；
- 首次响应明显延迟；
- 第二次请求再次创建成功；
- DB 出现两条业务结果。

## 6. 后续扩展

MVP 后再增加 OpenTelemetry/Trace、Prometheus、Kubernetes Events、Change History、Service Topology、Evidence Graph、多源时间线、批量并发采集。

## 7. 对接关系

| 对接模块 | 对方给你 | 你返回 | 联调要求 |
|---|---|---|---|
| Reasoning | EvidencePlan / EvidenceRequest | Evidence[] | 不接受“帮我查查”式自由文本 |
| Knowledge | 组件/版本/已知故障上下文 | 现场 Evidence | 先验知识不能当 Evidence |
| Runtime | 调度、超时策略 | 标准 Evidence | 失败必须标准错误码 |
| Reproduction | 实验期间观测目标 | 实验证据 | 时间范围必须对应 Experiment |
| Integration | MCP 调用验证 | Observability MCP | MCP 只执行工具，不承担 Evidence Planning/根因判断 |

## 8. 测试要求

至少覆盖：正常 Evidence、空结果、外部系统超时、权限失败、服务不可用、Batch 部分成功、raw_ref、时间窗口、Evidence ID、supports/contradicts、不存在 Hypothesis ID。

建议：

```text
tests/investigation/test_collect.py
tests/investigation/test_collect_batch.py
tests/investigation/test_http_evidence_adapter.py
tests/investigation/test_log_adapter.py
tests/investigation/test_db_adapter.py
tests/investigation/test_timeout.py
tests/investigation/test_source_unavailable.py
tests/investigation/test_real_investigation_port_contract.py
```

## 9. 独立验收

组合：`FakeKnowledge + FakeReasoning + RealInvestigation + FakeReproduction`，E2E 必须继续通过。

```bash
pytest tests/investigation -q
pytest tests/contracts -q
pytest tests/e2e/test_fake_incident_flow.py -q
ruff check .
mypy src
```

真实系统未接入部分必须明确列为“未验证项”。

## 10. 交付物

RealInvestigationEngine、HTTP/Log/DB 最小 Adapter、Observability MCP、Tool Ports 实现、Evidence 标准化、测试、模块文档、外部系统配置说明、验证记录。

最终验收：**输入标准 EvidenceRequest，稳定返回标准 Evidence；替换 Fake 后其他模块无需修改。**
