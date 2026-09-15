# Timeout + Retry → Duplicate Create MVP

> 状态：isolated MVP verified  
> 日期：2026-09-15  
> 范围：Step 12，仅接入首个 Case 必需的最小真实能力

## 1. 验证目标

验证下面的因果链，而不是建设通用可观测平台或浏览器/代理基础设施：

```text
识别 Order Service 2026.09-retry-enabled
  -> 加载 Product Skill + Troubleshooting Skill
  -> H-1：首次请求已成功，响应延迟触发重试
  -> 规划 HTTP / Log / Delay / SQLite / Page Evidence
  -> 首次 POST 提交数据库
  -> 延迟首次响应 80ms，客户端 20ms 超时
  -> 相同 business_id 自动重试一次
  -> SQLite 出现两条订单
  -> Verification CONFIRMED
  -> RCAReport + Case artifacts
```

Core Runtime、Contract 和 Port 均未为该 Case 创建旁路。状态仍由 Runtime 推进，Engine Adapter 只返回结构化结果。

## 2. 最小真实能力

| 层 | 本步实现 | 未扩展范围 |
|---|---|---|
| Knowledge | 仓库内版本化 JSON Fixture，带 SHA-256 原始引用 | Obsidian Vault、语义检索、远程知识库 |
| Skill | 从唯一 Canonical Skill Catalog 加载 `product-knowledge`、`troubleshooting` | 平台专属 Skill 分叉 |
| Reasoning | 可检查的固定规则；候选 Hypothesis 复用确定性 Reasoning Fake | 在线 LLM、自主开放式规划 |
| Investigation | 读取真实 HTTP JSONL、应用日志、SQLite 和页面事件 | 生产 Trace/Log/SQL Connector |
| Reproduction | FastAPI ASGI 后端、httpx 重试客户端、SQLite、提交后响应延迟 | Playwright、mitmproxy、Toxiproxy |
| Verification | 同时核对 HTTP 请求数与 SQLite 订单数 | 分布式一致性或生产流量验证 |

这里的“真实”表示实际执行了 HTTP ASGI 请求、异步超时/取消、FastAPI handler、SQLite commit 和文件证据采集；没有用预先写死的 ExperimentResult 代替实验。

## 3. 测试环境

测试后端故意不实现幂等：每个 `POST /orders` 都写入新订单。第一次请求按以下顺序执行：

1. 插入订单并 commit；
2. 写入 Request/Trace 和应用日志；
3. 延迟响应；
4. 客户端先超时并取消等待；
5. 客户端使用同一 `business_id` 和 `trace_id`、不同 `request_id` 重试；
6. 第二次请求再次写入订单并立即响应。

因此第一次客户端超时不会回滚已经完成的创建，准确覆盖目标故障机制。

## 4. 一键生命周期

开发者可执行：

```bash
.venv/bin/python -m ops_agent.integrations.timeout_retry_mvp build/timeout-retry-mvp
```

`TimeoutRetryMvpCase.execute()` 保证：

```text
setup -> run incident capture -> Runtime E2E -> verify -> persist -> cleanup
```

- setup 创建空 SQLite schema、FastAPI/httpx client 和证据文件；
- run 先捕获报告现场，再由 Runtime 完成完整分析与复现实验；
- reproduction prepare 自动清空测试表并重置序列，不依赖人工改库；
- verify 查询真实 SQLite 与 Request records；
- persist 写出实验、RCA 和 Case 摘要；
- cleanup 在成功或异常时都会关闭 HTTP client。

调用者负责选择/最终删除输出目录，以便 CI 可以保留失败证据。

## 5. 证据输出

| Artifact | 证明内容 |
|---|---|
| `requests.jsonl` | 两个 POST、相同 Trace ID、不同 Request ID、第一次延迟大于超时 |
| `application.log` | 两次 handler 均完成 `order_created` |
| `orders.sqlite3` | 相同 business_id 对应两个订单行 |
| `order-page.html` | 被测试客户端实际加载的最小订单页面 |
| `page-events.json` | `submit → timeout → retry → success` 页面/客户端观察序列 |
| `experiment-result.json` | 重试次数、两个请求 ID、两个订单 ID 和页面事件 |
| `rca-report.json` | 已确认事实、根因、修复建议、未验证项和证据链 |
| `case-summary.json` | 可索引的 Case 沉淀摘要 |

Evidence Contract 的 `raw_reference.uri` 指向实际 artifact，并保存采集时 SHA-256 摘要。

## 6. Done 标准

- 产品版本由 Knowledge Fixture 识别；
- Product/ Troubleshooting Canonical Skills 均可加载；
- Runtime 依次产生 Hypothesis、EvidencePlan、Evidence、ExperimentPlan、ExperimentResult、VerificationResult、RCAReport；
- 第一次请求先创建再超时；
- 客户端自动重试，无人工数据库写入；
- HTTP、Trace/Request ID、日志、SQLite、页面和实验结果均有独立证据；
- 验证为 `CONFIRMED`，Runtime 进入 `COMPLETED`；
- setup/run/verify/cleanup 可通过一个命令执行；
- 专项测试、全量测试、ruff 和 mypy 通过。

## 7. 明确未验证

- 没有安装或运行 Playwright，因此未验证真实浏览器 JavaScript、DOM 事件和截图；
- 没有安装或运行 mitmproxy/Toxiproxy，延迟由隔离 FastAPI Adapter 在 commit 后注入；
- 没有连接生产日志、Trace、数据库或真实订单服务；
- 没有验证生产环境网络延迟来源、消息队列链路和用户真实重复点击；
- 规则 Reasoning 尚未替换为在线 Local LLM；
- 当前 SQLite 为单进程测试数据库，不代表生产数据库的并发与事务语义。

这些能力不影响本 Case 的隔离因果验证，但进入下一阶段前必须按实际接入目标分别建立 Contract Test 与安全策略。
