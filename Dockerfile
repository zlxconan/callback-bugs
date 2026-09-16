FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --prefix=/install .


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPS_AGENT_ENV=production \
    OPS_AGENT_LOG_LEVEL=INFO \
    OPS_AGENT_BUILTIN_SKILLS_PATH=/opt/ops-agent/skills/builtin \
    OPS_AGENT_PRODUCT_SKILLS_PATH=/opt/ops-agent/plugins/product-skills \
    OPS_AGENT_SKILL_CORE_API=1.0

RUN groupadd --system --gid 10001 ops-agent \
    && useradd --system --uid 10001 --gid ops-agent --home-dir /opt/ops-agent ops-agent \
    && mkdir -p /opt/ops-agent/plugins/product-skills /opt/ops-agent/scripts \
    && chown -R ops-agent:ops-agent /opt/ops-agent

COPY --from=builder /install /usr/local
COPY --chown=ops-agent:ops-agent skills/builtin /opt/ops-agent/skills/builtin
COPY --chown=ops-agent:ops-agent scripts/verify_skill_installation.py /opt/ops-agent/scripts/

RUN chmod -R a-w /opt/ops-agent/skills/builtin

WORKDIR /opt/ops-agent
USER ops-agent

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2).read()"]

CMD ["uvicorn", "ops_agent.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
