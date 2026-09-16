"""KnowledgePort implementation backed by installable Product Plugin Skills."""

from pydantic import ValidationError

from ops_agent.contracts import (
    KnowledgeContext,
    KnowledgeQuery,
    ProblemContext,
    ProductContext,
    TroubleshootingContext,
)
from ops_agent.knowledge.domain import (
    InvalidProductSkillError,
    ProductSkillSpec,
    TroubleshootingSkillSpec,
    UnknownProductError,
    UnknownProductVersionError,
)
from ops_agent.knowledge.service.normalizer import KnowledgeNormalizer
from ops_agent.skill_runtime import (
    LoadedSkill,
    SkillProductNotInstalledError,
    SkillResolver,
    SkillType,
    SkillVersionNotInstalledError,
)


class RealKnowledgeEngine:
    """Resolve, validate, and normalize installed product knowledge plugins."""

    def __init__(
        self,
        resolver: SkillResolver,
        normalizer: KnowledgeNormalizer | None = None,
    ) -> None:
        self._resolver = resolver
        self._normalizer = normalizer or KnowledgeNormalizer()

    async def resolve_product(self, problem: ProblemContext) -> ProductContext:
        product, version = self._problem_scope(problem)
        skill = self._resolve(product, version, SkillType.PRODUCT)
        spec = self._product_spec(skill, product, version)
        return self._normalizer.product_context(problem, skill, spec)

    async def query_product_knowledge(self, query: KnowledgeQuery) -> KnowledgeContext:
        product, version = self._query_scope(query)
        skill = self._resolve(product, version, SkillType.PRODUCT)
        spec = self._product_spec(skill, product, version)
        return self._normalizer.knowledge_context(query, skill, spec)

    async def query_troubleshooting(self, query: KnowledgeQuery) -> TroubleshootingContext:
        product, version = self._query_scope(query)
        skill = self._resolve(product, version, SkillType.TROUBLESHOOTING)
        spec = self._troubleshooting_spec(skill, product, version)
        return self._normalizer.troubleshooting_context(query, skill, spec)

    def _resolve(self, product: str, version: str, skill_type: SkillType) -> LoadedSkill:
        try:
            return self._resolver.resolve(
                product=product,
                product_version=version,
                skill_type=skill_type,
            )
        except SkillProductNotInstalledError as error:
            raise UnknownProductError(str(error)) from error
        except SkillVersionNotInstalledError as error:
            raise UnknownProductVersionError(str(error)) from error

    @staticmethod
    def _problem_scope(problem: ProblemContext) -> tuple[str, str]:
        product = problem.environment.get("product")
        version = problem.environment.get("version")
        if not isinstance(product, str) or not product.strip():
            raise UnknownProductError(
                "ProblemContext.environment requires a non-empty string product"
            )
        if not isinstance(version, str) or not version.strip():
            raise UnknownProductVersionError(
                f"ProblemContext.environment requires a version for {product}"
            )
        return product, version

    @staticmethod
    def _query_scope(query: KnowledgeQuery) -> tuple[str, str]:
        if query.product is None:
            raise UnknownProductError("KnowledgeQuery requires resolved ProductContext")
        return query.product.product_name, query.product.product_version

    @staticmethod
    def _product_spec(
        skill: LoadedSkill,
        product: str,
        version: str,
    ) -> ProductSkillSpec:
        try:
            spec = ProductSkillSpec.model_validate(skill.content)
        except ValidationError as error:
            raise InvalidProductSkillError(
                f"Invalid PRODUCT payload for {skill.manifest.name}: {error}"
            ) from error
        context = spec.product_context
        if context.product_name != product or skill.manifest.product != product:
            raise InvalidProductSkillError(
                f"PRODUCT payload product_name {context.product_name!r} does not match "
                f"manifest product {product!r}"
            )
        if context.product_version != version or skill.manifest.product_versions != (
            context.product_version,
        ):
            raise InvalidProductSkillError(
                f"PRODUCT payload product_version {context.product_version!r} does not match "
                f"manifest/resolved versions {skill.manifest.product_versions!r}/{version!r}"
            )
        return spec

    @staticmethod
    def _troubleshooting_spec(
        skill: LoadedSkill,
        product: str,
        version: str,
    ) -> TroubleshootingSkillSpec:
        try:
            spec = TroubleshootingSkillSpec.model_validate(skill.content)
        except ValidationError as error:
            raise InvalidProductSkillError(
                f"Invalid TROUBLESHOOTING payload for {skill.manifest.name}: {error}"
            ) from error
        if spec.product != product or skill.manifest.product != product:
            raise InvalidProductSkillError(
                f"TROUBLESHOOTING payload product {spec.product!r} does not match "
                f"manifest product {product!r}"
            )
        if version not in spec.product_versions or set(spec.product_versions) != set(
            skill.manifest.product_versions
        ):
            raise InvalidProductSkillError(
                f"TROUBLESHOOTING payload product_versions {spec.product_versions!r} "
                f"do not include resolved version {version!r}"
            )
        return spec


# Compatibility name retained for callers introduced by Architecture Baseline v0.2.
PluginKnowledgeEngine = RealKnowledgeEngine
