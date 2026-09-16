import pytest

from ops_agent.knowledge.adapters import RealKnowledgeEngine
from ops_agent.knowledge.domain import UnknownProductError, UnknownProductVersionError
from ops_agent.ports import KnowledgePort

from .conftest import product_problem


@pytest.mark.asyncio
async def test_real_engine_resolves_installed_product_version(
    real_knowledge: RealKnowledgeEngine,
) -> None:
    assert isinstance(real_knowledge, KnowledgePort)

    product = await real_knowledge.resolve_product(product_problem())

    assert product.product_name == "TestProduct"
    assert product.product_version == "1.0"
    assert product.component == "create-api"
    assert product.source == "product-skill-plugin"
    assert product.metadata["skill_name"] == "test-product-product-v1"
    assert str(product.metadata["entrypoint_uri"]).endswith("/product/product.json")
    assert str(product.metadata["skill_digest"]).startswith("sha256:")


@pytest.mark.asyncio
async def test_unknown_product_is_explicit(real_knowledge: RealKnowledgeEngine) -> None:
    with pytest.raises(UnknownProductError, match="MissingProduct"):
        await real_knowledge.resolve_product(product_problem(product="MissingProduct"))


@pytest.mark.asyncio
async def test_unknown_version_is_explicit(real_knowledge: RealKnowledgeEngine) -> None:
    with pytest.raises(UnknownProductVersionError, match="TestProduct.*9.9"):
        await real_knowledge.resolve_product(product_problem(version="9.9"))
