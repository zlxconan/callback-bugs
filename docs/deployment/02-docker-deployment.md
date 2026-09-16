# Docker Build / Deployment / Packaging

> 适用版本：Ops Agent Core `0.1.0`，模块化单体部署。

## 1. 当前部署边界

Compose 只启动一个 `ops-agent` 服务。镜像安装完整 `ops_agent` Python package，因此包含
FastAPI、Core Runtime、四个 Engine、Skill Runtime 和 Runtime MCP Adapter，不拆分微服务。

当前 FastAPI 主入口是 `ops_agent.api.app:app`。容器环境设置 Product Skill 根目录后，入口会建立
单进程组合根并装配：

- Core Runtime + InMemoryStateRepository + SystemClock；
- Runtime MCP Registry；
- RealKnowledgeEngine + 外部 Product Plugin Registry；
- 当前已有的 FakeReasoningEngine、FakeInvestigationEngine、FakeReproductionEngine；
- 四个 Engine 的现有 FastAPI Router。

因此除了 `GET /health` 和 `GET /ready`，容器还公开各 Engine 已有的调试 Router。后三个 Engine
仍是 Fake，不应被描述为真实生产集成。

Runtime MCP 当前实现为进程内、传输无关的 `McpToolRegistry`，由 Python Agent Adapter 调用；仓库尚无
HTTP、SSE 或 stdio MCP Server。因此 Compose 不声明虚假的第二服务或 MCP 网络端口。需要远程 Agent
连接时，必须先在后续步骤实现并验证真实 MCP transport。

## 2. 镜像结构

镜像使用两个 `python:3.11-slim` 阶段：

```text
builder
└── /install/                         # 安装 ops-agent 及运行依赖

runtime (non-root uid/gid 10001)
└── /opt/ops-agent/
    ├── skills/builtin/               # 六个 Built-in，镜像内只读
    ├── plugins/product-skills/       # 外部只读 volume 挂载点
    └── scripts/verify_skill_installation.py
```

测试、TestProduct fixture、真实 Product Skill、Crawler Tool Skill、`.env` 和凭据均不复制进镜像。
容器文件系统设为只读，只提供 `/tmp` 临时文件系统。

## 3. 前置条件

- Docker Engine 和 Docker Compose v2；
- `8000/tcp` 未被占用；
- 外部 Product Skill Repository 对容器运行用户可读；
- Product Plugin 满足 `docs/interfaces/04-skill-plugin-spec.md`；
- Linux 服务器需同时检查 bind mount 的 SELinux/AppArmor 策略。

## 4. 配置环境变量

可选地复制示例配置：

```bash
cp .env.example .env
```

| 变量 | Compose 默认值 | 是否必须修改 | 作用 |
|---|---|---:|---|
| `OPS_AGENT_IMAGE` | `ops-agent-core:0.1.0` | 否 | 构建或加载的镜像 tag |
| `OPS_AGENT_PRODUCT_SKILLS_HOST_PATH` | `./runtime-data/product-skills` | 有真实插件时是 | Host Product Repository 根目录 |
| `OPS_AGENT_LOG_LEVEL` | `INFO` | 否 | 应用日志级别预留配置 |
| `OPS_AGENT_SKILL_CORE_API` | `1.0` | 仅兼容版本变化时 | Plugin Core API 校验版本 |

Compose 固定向容器传入：

```text
OPS_AGENT_BUILTIN_SKILLS_PATH=/opt/ops-agent/skills/builtin
OPS_AGENT_PRODUCT_SKILLS_PATH=/opt/ops-agent/plugins/product-skills
```

这些配置不是秘密。真实密码、Token、Repository 凭据不得写入 `.env`、镜像或 Skill Manifest。
`OPS_AGENT_ENV` 和 `OPS_AGENT_LOG_LEVEL` 已存在于项目配置，但当前应用没有日志配置加载器；它们暂不
改变业务行为。

## 5. 准备 Product Skill Repository

默认挂载点是空的：

```bash
mkdir -p runtime-data/product-skills
```

真实部署将 `.env` 中的 Host 路径改为外部 Repository：

```dotenv
OPS_AGENT_PRODUCT_SKILLS_HOST_PATH=/srv/ops-agent/product-skills
```

容器内始终挂载到 `/opt/ops-agent/plugins/product-skills:ro`。PRODUCT 和
TROUBLESHOOTING package 放在同一根目录，由 Manifest 类型区分。详细目录规范见
[Skill Installation](01-skill-installation.md)。

仅用于本地验收 TestProduct 时可以临时设置：

```bash
OPS_AGENT_PRODUCT_SKILLS_HOST_PATH="$PWD/tests/fixtures/product-skills" docker compose up -d
```

TestProduct 不进入镜像或正式离线交付包。

## 6. 构建与配置检查

```bash
docker build -t ops-agent-core:0.1.0 .
docker compose config
```

`docker compose config` 应只显示 `ops-agent` 一个服务、`8000` 一个公开端口，以及 Product Skill
只读 bind mount。

## 7. 一键启动

```bash
docker compose up -d
docker compose ps
```

Compose 使用 `unless-stopped` 重启策略。没有配置 demo/local-model profile，因为当前仓库没有可独立
部署的真实 Demo Lab 或 Local Model 服务。

## 8. 健康与就绪检查

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

预期分别返回：

```json
{"status":"ok"}
{"status":"ready"}
```

应用导入时会构建组合根并校验插件目录中的所有 Manifest；目录或插件非法会导致进程启动失败。
当前 `/ready` 只表达成功启动后的 FastAPI 进程就绪，不保证某个具体 product/version 已安装；目标产品
可用性必须用下一节的预检查确认。

## 9. Skill 加载验证

预检查要求目标产品具备 PRODUCT、TROUBLESHOOTING 和用于隔离验证的第二个 PRODUCT 版本：

```bash
docker compose exec ops-agent \
  python /opt/ops-agent/scripts/verify_skill_installation.py \
  --product TestProduct \
  --version 1.0 \
  --comparison-version 2.0
```

成功输出必须含 `"ok": true`。也可以检查 Built-in 是否已打入镜像：

```bash
docker compose exec ops-agent \
  python -c "from pathlib import Path; print(len(tuple(Path('/opt/ops-agent/skills/builtin').glob('*/skill.toml'))))"
```

预期为 `6`。镜像本身不应包含 TestProduct：

```bash
docker compose exec ops-agent \
  python -c "from pathlib import Path; print(any(Path('/opt/ops-agent').rglob('test-product-v1')))"
```

预期为 `False`；随后确认 Product 内容只会在 bind mount 目标下出现。

Runtime MCP 没有网络 transport，不能用 `curl` 验证。其现有可访问性由 Python 集成测试
`tests/integration/mcp/test_runtime_e2e.py` 验证；部署组合测试同时验证 Registry 已挂到
`app.state.runtime_mcp`。

## 10. 日志和生命周期

```bash
docker compose logs --tail=200 ops-agent
docker compose logs -f ops-agent
docker compose restart ops-agent
docker compose stop
docker compose down
```

重启后重新执行 `/health`、`/ready` 和 Skill 预检查。当前 Incident Repository 是进程内实现时，重启
不会保留 Incident 状态；容器部署并未增加持久化数据库。

## 11. 升级镜像

```bash
docker build -t ops-agent-core:0.1.1 .
OPS_AGENT_IMAGE=ops-agent-core:0.1.1 docker compose up -d --no-deps ops-agent
docker compose ps
```

健康检查通过后再清理旧镜像。不要覆盖正在运行的 tag 来隐藏版本变化。

## 12. 更新 Product Skill 而不重建镜像

1. 在 Host 的 staging 目录生成完整 Repository 发布版本；
2. 对 staging 内容执行 Skill 预检查；
3. 原子切换 `OPS_AGENT_PRODUCT_SKILLS_HOST_PATH` 指向的目录或其符号链接；
4. 执行 `docker compose restart ops-agent`，刷新进程内 Registry；
5. 再次执行 Skill 预检查。

当前没有文件 watcher，替换挂载内容后必须重启。不要在活动目录逐文件覆盖，以免发现混合版本。

移除 Product Plugin 后，Resolver 应返回明确的未安装错误；空 Repository 不会使 `/ready` 失败。

## 13. 离线交付包

联网构建机执行：

```bash
scripts/package_release.sh 0.1.0 dist
```

脚本执行 `docker build`、`docker save | gzip`，并生成：

```text
dist/ops-agent-core-0.1.0.tar.gz
└── ops-agent-core-0.1.0/
    ├── ops-agent-core-0.1.0.image.tar.gz
    ├── docker-compose.yml
    ├── .env.example
    ├── .env.release
    ├── product-skills/README.md
    └── docs/deployment/{01-skill-installation.md,02-docker-deployment.md}
```

交付包不包含真实 `.env`、真实 Product Skill 或 Tool Skill。Product Skill Repository 应作为独立、受控
制品交付。

内网机器执行：

```bash
tar -xzf ops-agent-core-0.1.0.tar.gz
cd ops-agent-core-0.1.0
gzip -dc ops-agent-core-0.1.0.image.tar.gz | docker load
cp .env.example .env
# 编辑 OPS_AGENT_PRODUCT_SKILLS_HOST_PATH，指向单独交付的插件目录
docker compose --env-file .env.release up -d --no-build
```

随后执行健康、就绪与 Skill 预检查。`.env.release` 只固定镜像 tag，不含秘密。

## 14. 故障排查

| 现象 | 检查 | 处理 |
|---|---|---|
| `docker compose up` 报 mount 错误 | Host 路径是否存在、权限和 SELinux label | 创建目录并授予只读访问；按平台配置 label |
| 容器持续 unhealthy | `docker compose logs ops-agent`、`/ready` | 检查 Uvicorn 是否监听 8000 |
| Built-in 数量不是 6 | 镜像 tag、Dockerfile COPY、路径变量 | 用正确 context 重建镜像 |
| Plugin not installed | bind mount、Manifest product/version | 安装精确版本并重启 |
| Plugin validation error | `skill.toml`、entrypoint、Core API | 按 Plugin Spec 修复制品 |
| 替换插件后仍返回旧内容 | Registry 只在装配时 refresh | 重启应用后复验 |
| `docker load` 后仍尝试构建 | Compose 含 build 定义 | 使用 `up -d --no-build` 并确认 `OPS_AGENT_IMAGE` |
| Runtime MCP 无网络地址 | 当前没有 MCP transport | 使用现有进程内 Adapter；远程接入留待后续交付步骤 |
