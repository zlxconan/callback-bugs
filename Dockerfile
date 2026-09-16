ARG OPS_AGENT_BASE_IMAGE=ops-agent-runtime-base:py311-playwright1.63

FROM ${OPS_AGENT_BASE_IMAGE} AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip wheel --no-deps --wheel-dir /wheels .


FROM ${OPS_AGENT_BASE_IMAGE} AS runtime

ENV OPS_AGENT_ENV=production \
    OPS_AGENT_LOG_LEVEL=INFO \
    OPS_AGENT_BUILTIN_SKILLS_PATH=/opt/ops-agent/skills/builtin \
    OPS_AGENT_PRODUCT_SKILLS_PATH=/opt/ops-agent/plugins/product-skills \
    OPS_AGENT_SKILL_CORE_API=1.0 \
    OPS_AGENT_MCP_ALLOWED_HOSTS=127.0.0.1:8000,localhost:8000 \
    OPS_AGENT_REPRODUCTION_SCREENSHOT_DIR=/tmp/ops-agent/screenshots

RUN groupadd --system --gid 10001 ops-agent \
    && useradd --system --uid 10001 --gid ops-agent --home-dir /opt/ops-agent ops-agent \
    && mkdir -p /opt/ops-agent/plugins/product-skills /opt/ops-agent/scripts \
    && chown -R ops-agent:ops-agent /opt/ops-agent

COPY --from=builder /wheels /tmp/wheels
RUN python -m pip install --no-deps /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels

COPY --chown=ops-agent:ops-agent skills/builtin /opt/ops-agent/skills/builtin
COPY --chown=ops-agent:ops-agent scripts/verify_skill_installation.py /opt/ops-agent/scripts/

RUN chmod -R a-w /opt/ops-agent/skills/builtin

WORKDIR /opt/ops-agent
USER ops-agent

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2).read()"]

CMD ["uvicorn", "ops_agent.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
