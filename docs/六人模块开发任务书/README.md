# 六人并行开发任务说明

本目录包含 6 份独立任务书，可直接发给对应成员，并让其 Codex / CodeBuddy 在开发前阅读。

## 分工

| 人员 | 模块 | 核心目标 |
|---|---|---|
| 张龙兴 | Knowledge Engine | 版本感知产品/故障知识 |
| 杨文魁 | Reasoning Engine | Planner/Hypothesis/Evidence Plan/Reflection |
| 张成 | Investigation Engine | 真实现场 Evidence 获取 |
| 王亚东 | Reproduction Engine | 实验、故障注入、复现与验证 |
| 连延斌 | Core Runtime / Contracts / Skill Runtime | 公共协议、状态机、插件生命周期和稳定性 |
| 赵瑞琴 | Integration / Agent / Eval | Canonical Skill Packaging 与多 Host 接入评测 |

## 统一协作主线

```text
ProblemContext
  ↓
Knowledge Engine → KnowledgeContext
  ↓
Reasoning Engine → HypothesisSet / EvidencePlan
  ↓
Investigation Engine → Evidence[]
  ↓
Reasoning Engine → RootCauseAssessment / ExperimentPlan
  ↓
Reproduction Engine → ExperimentResult / VerificationResult
  ↓
Runtime + Reasoning → RCAReport
```

## 全员共同规则

- 技术基线：Python 3.11+ / FastAPI / LangChain / Pydantic v2 / pytest / pytest-asyncio / httpx / ruff / mypy。
- 开发前必须阅读根目录 `AGENTS.md`。
- Engine 之间禁止直接 import 对方实现，只能通过 Contract + Port 对接。
- `contracts/`、核心 `ports/`、公共错误码、Runtime 状态机属于公共基线，未经接口评审不得直接修改。
- FastAPI 仅用于 API/Adapter 层；Domain/Core 不依赖 FastAPI。
- LangChain 仅用于 LLM/Agent/Tool Adapter 层；Contracts/Core/Domain 不依赖 LangChain。
- 每个任务先定义测试与验收条件，再写实现。
- 每个 Real Engine 的第一验收目标都是：**可直接替换对应 Fake Engine，且完整 Fake E2E 不回退。**
- Mock/Fake 验证通过不能等价为真实环境验证通过。
- Product/Troubleshooting Plugin 只由 Knowledge Engine 经 Skill Runtime 解析；Reasoning 不读取插件文件。
- Crawler/Parser Tool Skill 属于外部知识生产链，不进入 Incident Runtime。

## 推荐分支

```text
feature/knowledge
feature/reasoning
feature/investigation
feature/reproduction
feature/runtime
feature/integration-eval
```

## 第一阶段共同 MVP

统一只围绕一个 Case：

> 首次请求实际成功，但响应延迟导致客户端自动重试，最终发生重复创建。

目标不是先把各模块做“大而全”，而是让 6 个模块共同跑通第一条真实闭环。
