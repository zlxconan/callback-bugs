"""KnowledgePort adapter backed by installable Product Plugin Skills."""

from pydantic import JsonValue

from ops_agent.contracts import (
    KnowledgeContext,
    KnowledgeQuery,
    ProblemContext,
    ProductContext,
    RawReference,
    TroubleshootingContext,
)
from ops_agent.skill_runtime import LoadedSkill, SkillResolver, SkillType


class PluginKnowledgeEngine:
    """Normalize external Product Plugin data into stable Knowledge Contracts."""

    def __init__(self, resolver: SkillResolver) -> None:
        self._resolver = resolver

    async def resolve_product(self, problem: ProblemContext) -> ProductContext:
        product, version = self._problem_scope(problem)
        skill = self._resolver.resolve(
            product=product,
            product_version=version,
            skill_type=SkillType.PRODUCT,
        )
        content = self._object_content(skill)
        context = self._object_value(content, "product_context")
        return ProductContext.model_validate(
            {
                **self._base(problem, skill),
                **context,
            }
        )

    async def query_product_knowledge(self, query: KnowledgeQuery) -> KnowledgeContext:
        if query.product is None:
            raise ValueError("KnowledgeQuery requires resolved ProductContext")
        skill = self._resolver.resolve(
            product=query.product.product_name,
            product_version=query.product.product_version,
            skill_type=SkillType.PRODUCT,
        )
        content = self._object_content(skill)
        knowledge = self._object_value(content, "knowledge")
        return KnowledgeContext.model_validate(
            {
                **self._base(query, skill),
                "query": query.query,
                "facts": knowledge.get("facts", []),
                "references": [
                    RawReference(
                        uri=skill.entrypoint.as_uri(),
                        digest=skill.digest,
                        media_type="application/json",
                    )
                ],
                "skill_ids": [skill.manifest.name],
                "limitations": knowledge.get("limitations", []),
            }
        )

    async def query_troubleshooting(self, query: KnowledgeQuery) -> TroubleshootingContext:
        if query.product is None:
            raise ValueError("KnowledgeQuery requires resolved ProductContext")
        skill = self._resolver.resolve(
            product=query.product.product_name,
            product_version=query.product.product_version,
            skill_type=SkillType.TROUBLESHOOTING,
        )
        content = self._object_content(skill)
        return TroubleshootingContext.model_validate(
            {
                **self._base(query, skill),
                **content,
            }
        )

    @staticmethod
    def _problem_scope(problem: ProblemContext) -> tuple[str, str]:
        product = problem.environment.get("product")
        version = problem.environment.get("version")
        if not isinstance(product, str) or not isinstance(version, str):
            raise ValueError("ProblemContext.environment requires string product and version")
        return product, version

    @staticmethod
    def _object_content(skill: LoadedSkill) -> dict[str, JsonValue]:
        if not isinstance(skill.content, dict):
            raise ValueError(f"Plugin content must be a JSON object: {skill.manifest.name}")
        return skill.content

    @staticmethod
    def _object_value(
        content: dict[str, JsonValue],
        field: str,
    ) -> dict[str, JsonValue]:
        value = content.get(field)
        if not isinstance(value, dict):
            raise ValueError(f"Plugin field must be an object: {field}")
        return value

    @staticmethod
    def _base(
        contract: ProblemContext | KnowledgeQuery,
        skill: LoadedSkill,
    ) -> dict[str, JsonValue]:
        return {
            "schema_version": contract.schema_version,
            "incident_id": contract.incident_id,
            "request_id": contract.request_id,
            "timestamp": contract.timestamp.isoformat(),
            "source": "product-skill-plugin",
            "metadata": {
                "skill_name": skill.manifest.name,
                "skill_version": skill.manifest.version,
                "skill_digest": skill.digest,
            },
        }
