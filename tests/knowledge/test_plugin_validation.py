import json
from pathlib import Path

import pytest

from ops_agent.knowledge.adapters import RealKnowledgeEngine
from ops_agent.knowledge.domain import InvalidProductSkillError
from ops_agent.skill_runtime import (
    SkillLoader,
    SkillRegistry,
    SkillResolver,
    SkillValidationError,
)

from .conftest import product_problem


def write_plugin(
    root: Path,
    *,
    directory: str,
    name: str,
    versions: str,
    payload_version: str,
) -> None:
    package = root / directory
    package.mkdir(parents=True)
    (package / "skill.toml").write_text(
        "\n".join(
            [
                'schema_version = "1.0"',
                f'name = "{name}"',
                'skill_type = "PRODUCT"',
                'version = "1.0.0"',
                'product = "TestProduct"',
                f"product_versions = [{versions}]",
                'entrypoint = "product.json"',
                'core_api = "1.0"',
            ]
        ),
        encoding="utf-8",
    )
    payload = {
        "schema_version": "1.0",
        "product_context": {
            "product_name": "TestProduct",
            "product_version": payload_version,
            "component": "create-api",
            "deployment_environment": "test",
            "expected_behavior": "Synthetic behavior.",
            "configuration": {},
        },
        "features": [{"id": "create-order", "description": "Create an order."}],
        "retry_behavior": {
            "enabled": True,
            "max_retries": 1,
            "description": "Retry once.",
        },
        "known_issues": [],
        "limitations": ["Synthetic fixture."],
    }
    (package / "product.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_manifest_and_payload_product_versions_must_match(tmp_path: Path) -> None:
    write_plugin(
        tmp_path,
        directory="mismatch",
        name="test-product-mismatch",
        versions='"1.0"',
        payload_version="2.0",
    )
    registry = SkillRegistry(SkillLoader(tmp_path))
    registry.refresh()
    engine = RealKnowledgeEngine(SkillResolver(registry))

    with pytest.raises(InvalidProductSkillError, match="product_version"):
        await engine.resolve_product(product_problem(version="1.0"))


def test_overlapping_product_versions_are_rejected(tmp_path: Path) -> None:
    write_plugin(
        tmp_path,
        directory="one",
        name="test-product-one",
        versions='"1.0", "2.0"',
        payload_version="1.0",
    )
    write_plugin(
        tmp_path,
        directory="two",
        name="test-product-two",
        versions='"2.0"',
        payload_version="2.0",
    )

    with pytest.raises(SkillValidationError, match="overlapping"):
        SkillRegistry(SkillLoader(tmp_path)).refresh()
