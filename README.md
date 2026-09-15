# Ops Agent

AI 辅助线上问题分析与复现 Agent。当前项目采用 Python 3.11+、src layout 和模块化单体架构。

当前仅包含统一工程骨架与健康检查接口，不包含 Knowledge、Reasoning、Investigation 或 Reproduction 业务逻辑。

## 开发环境

推荐使用 `uv` 创建隔离环境：

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e '.[dev]'
```

也可以使用已有的 Python 3.11+：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## 启动 API

```bash
uvicorn ops_agent.api.app:app --reload
```

启动后可访问：

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/ready`

## 质量检查

```bash
ruff check .
ruff format --check .
mypy
pytest
```

架构方案见 [`docs/architecture/00-architecture-plan.md`](docs/architecture/00-architecture-plan.md)。

