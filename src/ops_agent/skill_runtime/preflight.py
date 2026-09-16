"""Read-only pre-deployment verification for installed Skill packages."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from ops_agent.contracts import IncidentSeverity, KnowledgeQuery, ProblemContext
from ops_agent.skill_runtime.config import SkillInstallationConfig
from ops_agent.skill_runtime.manifest import SkillType
from ops_agent.skill_runtime.registry import SkillProductNotInstalledError

EXPECTED_BUILTIN_SKILLS = frozenset(
    {
        "incident-analysis",
        "hypothesis-generation",
        "evidence-planning",
        "reflection",
        "reproduction-planning",
        "rca-report",
    }
)


class SkillInstallationVerification(BaseModel):
    """Machine-readable preflight evidence without plugin content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    builtin_skill_names: tuple[str, ...]
    product_skill_name: str
    troubleshooting_skill_name: str
    comparison_skill_name: str
    knowledge_fact_count: int
    missing_product_error_verified: bool
    tool_skills_excluded: bool


async def verify_skill_installation(
    config: SkillInstallationConfig,
    *,
    product: str,
    product_version: str,
    comparison_version: str,
) -> SkillInstallationVerification:
    """Verify discovery, version isolation, error behavior, and Knowledge loading."""

    # Delayed import avoids making the generic Skill Runtime depend on Knowledge at import time.
    from ops_agent.bootstrap.skills import build_skill_installation

    installation = build_skill_installation(config)
    builtin_names = tuple(sorted(skill.manifest.name for skill in installation.builtin_skills))
    if set(builtin_names) != EXPECTED_BUILTIN_SKILLS:
        raise ValueError(
            f"Built-in Skill set mismatch: expected {sorted(EXPECTED_BUILTIN_SKILLS)}, "
            f"found {list(builtin_names)}"
        )

    primary = installation.resolver.resolve(
        product=product,
        product_version=product_version,
        skill_type=SkillType.PRODUCT,
    )
    troubleshooting = installation.resolver.resolve(
        product=product,
        product_version=product_version,
        skill_type=SkillType.TROUBLESHOOTING,
    )
    comparison = installation.resolver.resolve(
        product=product,
        product_version=comparison_version,
        skill_type=SkillType.PRODUCT,
    )
    if primary.manifest.name == comparison.manifest.name or primary.digest == comparison.digest:
        raise ValueError("Product versions are not isolated")

    missing_product_verified = False
    try:
        installation.resolver.resolve(
            product="__ops_agent_preflight_missing_product__",
            product_version="0",
            skill_type=SkillType.PRODUCT,
        )
    except SkillProductNotInstalledError:
        missing_product_verified = True

    now = datetime.now(UTC)
    problem = ProblemContext(
        incident_id="INC-SKILL-PREFLIGHT",
        request_id="REQ-SKILL-PREFLIGHT",
        timestamp=now,
        source="skill-installation-preflight",
        title="Validate installed product knowledge",
        description="Read-only pre-deployment Product Skill verification.",
        symptoms=["preflight"],
        severity=IncidentSeverity.LOW,
        observed_at=now,
        affected_services=[],
        environment={"product": product, "version": product_version},
    )
    product_context = await installation.knowledge.resolve_product(problem)
    query = KnowledgeQuery(
        incident_id=problem.incident_id,
        request_id=problem.request_id,
        timestamp=now,
        source="skill-installation-preflight",
        problem=problem,
        product=product_context,
        query="pre-deployment validation",
    )
    knowledge = await installation.knowledge.query_product_knowledge(query)
    await installation.knowledge.query_troubleshooting(query)
    tool_skills_excluded = {item.value for item in SkillType} == {
        "BUILTIN_METHOD",
        "PRODUCT",
        "TROUBLESHOOTING",
    }

    return SkillInstallationVerification(
        ok=missing_product_verified and tool_skills_excluded and bool(knowledge.facts),
        builtin_skill_names=builtin_names,
        product_skill_name=primary.manifest.name,
        troubleshooting_skill_name=troubleshooting.manifest.name,
        comparison_skill_name=comparison.manifest.name,
        knowledge_fact_count=len(knowledge.facts),
        missing_product_error_verified=missing_product_verified,
        tool_skills_excluded=tool_skills_excluded,
    )
