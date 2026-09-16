"""Normalize validated plugin payloads into frozen public Contracts."""

from collections.abc import Iterable

from pydantic import JsonValue

from ops_agent.contracts import (
    ContractBase,
    KnowledgeContext,
    KnowledgeQuery,
    ProblemContext,
    ProductContext,
    RawReference,
    TroubleshootingContext,
)
from ops_agent.knowledge.domain.plugin_specs import (
    ProductSkillSpec,
    TroubleshootingSkillSpec,
)
from ops_agent.skill_runtime import LoadedSkill


class KnowledgeNormalizer:
    """The only mapping from plugin-owned schemas to cross-module contexts."""

    def product_context(
        self,
        problem: ProblemContext,
        skill: LoadedSkill,
        spec: ProductSkillSpec,
    ) -> ProductContext:
        return ProductContext.model_validate(
            {
                **self._base(problem, skill),
                **spec.product_context.model_dump(mode="json"),
            }
        )

    def knowledge_context(
        self,
        query: KnowledgeQuery,
        skill: LoadedSkill,
        spec: ProductSkillSpec,
    ) -> KnowledgeContext:
        facts = [feature.description for feature in spec.features]
        facts.append(spec.retry_behavior.description)
        facts.extend(issue.description for issue in spec.known_issues)
        return KnowledgeContext.model_validate(
            {
                **self._base(query, skill),
                "query": query.query,
                "facts": facts,
                "references": [self._reference(skill).model_dump(mode="json")],
                "skill_ids": [skill.manifest.name],
                "limitations": list(spec.limitations),
            }
        )

    def troubleshooting_context(
        self,
        query: KnowledgeQuery,
        skill: LoadedSkill,
        spec: TroubleshootingSkillSpec,
    ) -> TroubleshootingContext:
        return TroubleshootingContext.model_validate(
            {
                **self._base(query, skill),
                "actions_taken": [],
                "observed_results": [],
                "known_workarounds": self._unique(
                    item for fault in spec.faults for item in fault.known_workarounds
                ),
                "constraints": self._unique(
                    item for fault in spec.faults for item in fault.constraints
                ),
            }
        )

    @staticmethod
    def _base(contract: ContractBase, skill: LoadedSkill) -> dict[str, JsonValue]:
        manifest = skill.manifest
        return {
            "schema_version": contract.schema_version,
            "incident_id": contract.incident_id,
            "request_id": contract.request_id,
            "timestamp": contract.timestamp.isoformat(),
            "source": "product-skill-plugin",
            "metadata": {
                "skill_name": manifest.name,
                "skill_version": manifest.version,
                "skill_type": manifest.skill_type.value,
                "product": manifest.product or "",
                "product_versions": list(manifest.product_versions),
                "entrypoint_uri": skill.entrypoint.as_uri(),
                "skill_digest": skill.digest,
            },
        }

    @staticmethod
    def _reference(skill: LoadedSkill) -> RawReference:
        return RawReference(
            uri=skill.entrypoint.as_uri(),
            digest=skill.digest,
            media_type="application/json",
        )

    @staticmethod
    def _unique(values: Iterable[str]) -> list[str]:
        return list(dict.fromkeys(values))
