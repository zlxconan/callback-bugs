# Timeout + Retry → Duplicate Create MVP

该目录沉淀 Step 12 的版本知识 Fixture。可执行 Case 位于
`ops_agent.integrations.timeout_retry_mvp`，一条命令运行完整生命周期：

```bash
.venv/bin/python -m ops_agent.integrations.timeout_retry_mvp build/timeout-retry-mvp
```

输出目录包含：

- `requests.jsonl`：HTTP 方法、路径、业务标识、Trace ID、Request ID 和响应延迟；
- `application.log`：两次实际创建日志；
- `orders.sqlite3`：无需人工改动的最终测试数据库；
- `order-page.html` / `page-events.json`：页面和客户端观察到的行为；
- `experiment-result.json`：结构化实验结果；
- `rca-report.json`：Runtime 生成的结构化 RCA；
- `case-summary.json`：Case、证据和未验证项摘要。

输出目录由调用者选择；环境 cleanup 会关闭 HTTP client，但保留证据文件供分析。
