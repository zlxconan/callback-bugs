from datetime import UTC, datetime
from pathlib import Path

import pytest

from ops_agent.contracts import (
    IncidentSeverity,
    KnowledgeQuery,
    ProblemContext,
)
from ops_agent.knowledge.adapters import PluginKnowledgeEngine
from ops_agent.ports import KnowledgePort
from ops_agent.skill_runtime import (
    SkillLoader,
    SkillNotInstalledError,
    SkillRegistry,
    SkillResolver,
    SkillType,
    SkillValidationError,
)

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "product-skills"
BUILTIN_ROOT = Path(__file__).parents[2] / "skills" / "builtin"
NOW = datetime(2026, 9, 16, 1, 0, tzinfo=UTC)


def registry() -> SkillRegistry:
    value = SkillRegistry(SkillLoader(FIXTURE_ROOT))
    value.refresh()
    return value


def problem(version: str) -> ProblemContext:
    return ProblemContext(
        incident_id="INC-SKILL-RUNTIME",
        request_id="REQ-SKILL-RUNTIME",
        timestamp=NOW,
        source="skill-runtime-test",
        title="TestProduct create request failed",
        description="Resolve product-version knowledge from an installed test plugin.",
        symptoms=["create request failed"],
        severity=IncidentSeverity.MEDIUM,
        observed_at=NOW,
        affected_services=["create-api"],
        environment={"product": "TestProduct", "version": version},
    )


def test_builtin_and_product_skill_types_are_distinct() -> None:
    builtins = SkillLoader(BUILTIN_ROOT).discover()
    plugins = SkillLoader(FIXTURE_ROOT).discover()

    assert builtins
    assert {item.manifest.skill_type for item in builtins} == {SkillType.BUILTIN_METHOD}
    assert {item.manifest.skill_type for item in plugins} == {
        SkillType.PRODUCT,
        SkillType.TROUBLESHOOTING,
    }


def test_product_plugins_are_discovered_and_versions_are_isolated() -> None:
    resolver = SkillResolver(registry())

    version_one = resolver.resolve(
        product="TestProduct",
        product_version="1.0",
        skill_type=SkillType.PRODUCT,
    )
    version_two = resolver.resolve(
        product="TestProduct",
        product_version="2.0",
        skill_type=SkillType.PRODUCT,
    )

    assert version_one.manifest.name == "test-product-product-v1"
    assert version_two.manifest.name == "test-product-product-v2"
    assert version_one.content != version_two.content


def test_missing_product_plugin_has_explicit_error() -> None:
    with pytest.raises(SkillNotInstalledError, match="MissingProduct.*9.9"):
        SkillResolver(registry()).resolve(
            product="MissingProduct",
            product_version="9.9",
            skill_type=SkillType.PRODUCT,
        )


def test_registry_install_and_uninstall_are_in_memory_and_reversible() -> None:
    value = registry()
    installed = value.list(skill_type=SkillType.PRODUCT)[0]

    removed = value.uninstall(installed.manifest.name)
    with pytest.raises(SkillNotInstalledError):
        SkillResolver(value).resolve(
            product=installed.manifest.product or "",
            product_version=installed.manifest.product_versions[0],
            skill_type=SkillType.PRODUCT,
        )

    value.install(removed)
    restored = SkillResolver(value).resolve(
        product=installed.manifest.product or "",
        product_version=installed.manifest.product_versions[0],
        skill_type=SkillType.PRODUCT,
    )
    assert restored.manifest.name == installed.manifest.name


def test_registry_rejects_duplicate_manifest_names(tmp_path: Path) -> None:
    first = FIXTURE_ROOT / "test-product-v1" / "product"
    second = FIXTURE_ROOT / "test-product-v2" / "product"
    for index, source in enumerate((first, second), start=1):
        destination = tmp_path / str(index)
        destination.mkdir()
        manifest = (source / "skill.toml").read_text(encoding="utf-8")
        manifest = manifest.replace(
            f'name = "test-product-product-v{index}"',
            'name = "duplicate-product-name"',
        )
        (destination / "skill.toml").write_text(manifest, encoding="utf-8")
        (destination / "product.json").write_text(
            (source / "product.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    with pytest.raises(SkillValidationError, match="name"):
        SkillRegistry(SkillLoader(tmp_path)).refresh()


@pytest.mark.asyncio
async def test_installed_product_plugin_is_queryable_through_knowledge_port() -> None:
    engine = PluginKnowledgeEngine(SkillResolver(registry()))
    assert isinstance(engine, KnowledgePort)

    product_context = await engine.resolve_product(problem("1.0"))
    query = KnowledgeQuery(
        incident_id="INC-SKILL-RUNTIME",
        request_id="REQ-SKILL-RUNTIME",
        timestamp=NOW,
        source="skill-runtime-test",
        problem=problem("1.0"),
        product=product_context,
        query="create retry behavior",
    )
    knowledge = await engine.query_product_knowledge(query)
    troubleshooting = await engine.query_troubleshooting(query)

    assert product_context.product_version == "1.0"
    assert knowledge.skill_ids == ["test-product-product-v1"]
    assert knowledge.references[0].uri.endswith("/test-product-v1/product/product.json")
    assert troubleshooting.known_workarounds
