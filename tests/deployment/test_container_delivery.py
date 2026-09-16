"""Static acceptance tests for the container and offline delivery contract."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_dockerfile_keeps_runtime_small_and_non_root() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.count("FROM python:3.11-slim") == 2
    assert "COPY --from=builder /install /usr/local" in dockerfile
    assert "COPY --chown=ops-agent:ops-agent skills/builtin" in dockerfile
    assert "USER ops-agent" in dockerfile
    assert "tests/fixtures" not in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "ops_agent.api.app:app" in dockerfile


def test_dockerignore_excludes_non_runtime_assets_but_keeps_builtin_skills() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert ".git" in dockerignore
    assert ".env" in dockerignore
    assert "tests" in dockerignore
    assert "runtime-data/product-skills" in dockerignore
    assert "skills/builtin" not in dockerignore


def test_compose_has_one_core_service_and_read_only_product_mount() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "ops-agent:" in compose
    assert "8000:8000" in compose
    assert "/opt/ops-agent/plugins/product-skills:ro" in compose
    assert "OPS_AGENT_BUILTIN_SKILLS_PATH: /opt/ops-agent/skills/builtin" in compose
    assert "OPS_AGENT_PRODUCT_SKILLS_PATH: /opt/ops-agent/plugins/product-skills" in compose
    assert "test-product" not in compose.lower()
    assert "healthcheck:" in compose


def test_release_packaging_script_has_valid_shell_syntax() -> None:
    script = ROOT / "scripts" / "package_release.sh"

    result = subprocess.run(
        ["bash", "-n", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    content = script.read_text(encoding="utf-8")
    assert "docker build" in content
    assert "docker save" in content
    assert "gzip" in content
    assert ".env.example" in content
    assert "docker-compose.yml" in content
    assert "01-skill-installation.md" in content
    assert "02-docker-deployment.md" in content
