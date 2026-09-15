# Knowledge Engine 模块模板

> 状态：Step 6 template complete  
> 默认运行方式：模块化单体、进程内 Port 调用

## 职责

Knowledge Engine 负责解析产品、版本和组件上下文，查询版本适用的产品知识与故障排查知识，并通过结构化 Contract 返回知识来源、事实、限制和 Skill 标识。

## 非职责

本模块不编排 Incident，不生成根因假设，不采集现场证据，不执行复现实验，也不保存 Runtime 权威状态。HTTP Router 不是 Runtime 的内部调用链。

## 输入与输出

| 操作 | 输入 | 输出 |
|---|---|---|
| `resolve_product` | `ProblemContext` | `ProductContext` |
| `query_product_knowledge` | `KnowledgeQuery` | `KnowledgeContext` |
| `query_troubleshooting` | `KnowledgeQuery` | `TroubleshootingContext` |
| `health` | 无 | `ModuleHealth` |

## Ports 与调用方式

公共边界是 `KnowledgePort`。`KnowledgeService` 结构化实现该 Protocol，Core Runtime 或组合根应向其注入一个 `KnowledgePort` Adapter，并直接进行 async Python 调用：

```text
Core Runtime -> KnowledgeService -> KnowledgePort adapter
debug client -> FastAPI Router -> KnowledgeService
```

未来拆服务时仅替换入站装配与 Adapter；Service、Domain 及公共 Contract 不因 HTTP 传输而改变。

## Adapters、配置与错误

- `adapters/fake.py`：当前确定性 Fake。
- `adapters/`：未来 Obsidian、Git 知识源或 LangChain 边界；LangChain 类型必须在 Adapter 内终止。
- `domain/config.py`：冻结的 `KnowledgeConfig`，当前包含启用开关与 adapter 名称。
- `domain/errors.py`：模块错误、禁用错误和可重试依赖错误。
- `api/errors.py`：只在 HTTP 边界将模块错误映射为 `ErrorResponse`。
- `api/router.py`：`/knowledge/*` 调试端点与 `/knowledge/health`。

## 测试

- `tests/knowledge/test_module.py`：Service/Port/Fake/禁用配置单元测试。
- `tests/knowledge/test_contract.py`：FastAPI 请求响应、ModuleHealth 与 ErrorResponse Contract 测试。
- 全局架构测试继续禁止 domain、contracts、ports、core 引入 LangChain/FastAPI。

## MVP

MVP 仅使用 `FakeKnowledgeEngine` 返回 Step 5 的订单重试和非幂等知识，不连接真实知识库或 LLM。

## Done 标准

Knowledge 变更完成必须满足：所有 Port 方法使用公共 Contract；Service 可通过 Fake 独立运行；Router 可单独挂载调试；错误可映射；模块健康可查询；模块测试、Contract 测试、ruff、mypy 与全量 pytest 全部通过。

## 后续负责人开发目录

- 领域配置与错误：`src/ops_agent/knowledge/domain/`
- 用例入口：`src/ops_agent/knowledge/service/`
- 公共入口重导出：`src/ops_agent/knowledge/ports/`
- 外部知识与 LangChain 边界：`src/ops_agent/knowledge/adapters/`
- HTTP 调试层：`src/ops_agent/knowledge/api/`
- 测试：`tests/knowledge/`

