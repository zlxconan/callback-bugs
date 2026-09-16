import pytest

from ops_agent.contracts import (
    KnowledgeContext,
    KnowledgeQuery,
    ProblemContext,
    ProductContext,
    TroubleshootingContext,
)
from ops_agent.knowledge.adapters import RealKnowledgeEngine

from .conftest import NOW, product_problem


@pytest.mark.asyncio
async def test_product_and_troubleshooting_plugins_are_normalized_with_provenance(
    real_knowledge: RealKnowledgeEngine,
) -> None:
    problem = product_problem()
    product = await real_knowledge.resolve_product(problem)
    query = KnowledgeQuery(
        incident_id=problem.incident_id,
        request_id=problem.request_id,
        timestamp=NOW,
        source="real-knowledge-test",
        problem=problem,
        product=product,
        query="create-order timeout retry duplicate create risk",
    )

    knowledge = await real_knowledge.query_product_knowledge(query)
    troubleshooting = await real_knowledge.query_troubleshooting(query)

    assert any("automatic retry" in fact for fact in knowledge.facts)
    assert any("duplicate create" in fact for fact in knowledge.facts)
    assert knowledge.skill_ids == ["test-product-product-v1"]
    assert knowledge.references[0].uri.endswith("/product/product.json")
    assert knowledge.references[0].digest is not None
    assert knowledge.references[0].digest.startswith("sha256:")
    assert knowledge.model_validate_json(knowledge.model_dump_json()) == knowledge
    assert isinstance(KnowledgeContext.model_validate(knowledge.model_dump()), KnowledgeContext)

    assert troubleshooting.actions_taken == []
    assert troubleshooting.observed_results == []
    assert any("idempotency" in item for item in troubleshooting.known_workarounds)
    assert troubleshooting.metadata["skill_type"] == "TROUBLESHOOTING"
    assert str(troubleshooting.metadata["entrypoint_uri"]).endswith(
        "/troubleshooting/troubleshooting.json"
    )
    assert (
        TroubleshootingContext.model_validate_json(troubleshooting.model_dump_json())
        == troubleshooting
    )


@pytest.mark.asyncio
async def test_product_versions_are_isolated(real_knowledge: RealKnowledgeEngine) -> None:
    version_one_problem = product_problem(version="1.0")
    version_two_problem = product_problem(version="2.0")
    version_one = await real_knowledge.resolve_product(version_one_problem)
    version_two = await real_knowledge.resolve_product(version_two_problem)

    async def query(
        problem: ProblemContext,
        product: ProductContext,
    ) -> KnowledgeContext:
        return await real_knowledge.query_product_knowledge(
            KnowledgeQuery(
                incident_id=problem.incident_id,
                request_id=problem.request_id,
                timestamp=NOW,
                source="real-knowledge-test",
                problem=problem,
                product=product,
                query="create-order behavior",
            )
        )

    knowledge_one = await query(version_one_problem, version_one)
    knowledge_two = await query(version_two_problem, version_two)

    assert version_one.product_version == "1.0"
    assert version_two.product_version == "2.0"
    assert knowledge_one.skill_ids == ["test-product-product-v1"]
    assert knowledge_two.skill_ids == ["test-product-product-v2"]
    assert knowledge_one.facts != knowledge_two.facts
    assert not any("duplicate create" in fact for fact in knowledge_two.facts)
