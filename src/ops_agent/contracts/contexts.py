"""Problem, product, knowledge, and troubleshooting context contracts."""

from pydantic import AwareDatetime, Field, JsonValue

from ops_agent.contracts.base import ContractBase, NonEmptyString, RawReference
from ops_agent.contracts.enums import IncidentSeverity


class ProblemContext(ContractBase):
    """Normalized incident symptoms and impact supplied to the runtime."""

    title: NonEmptyString
    description: NonEmptyString
    symptoms: list[NonEmptyString] = Field(min_length=1)
    severity: IncidentSeverity
    observed_at: AwareDatetime
    affected_services: list[NonEmptyString] = Field(default_factory=list)
    environment: dict[str, JsonValue] = Field(default_factory=dict)


class ProductContext(ContractBase):
    """Product/version facts needed to decide expected behavior."""

    product_name: NonEmptyString
    product_version: NonEmptyString
    component: NonEmptyString
    deployment_environment: NonEmptyString
    expected_behavior: NonEmptyString
    configuration: dict[str, JsonValue] = Field(default_factory=dict)


class KnowledgeContext(ContractBase):
    """Version-scoped knowledge returned by a knowledge provider."""

    query: NonEmptyString
    facts: list[NonEmptyString] = Field(default_factory=list)
    references: list[RawReference] = Field(default_factory=list)
    skill_ids: list[NonEmptyString] = Field(default_factory=list)
    limitations: list[NonEmptyString] = Field(default_factory=list)


class TroubleshootingContext(ContractBase):
    """Troubleshooting history and constraints known before planning."""

    actions_taken: list[NonEmptyString] = Field(default_factory=list)
    observed_results: list[NonEmptyString] = Field(default_factory=list)
    known_workarounds: list[NonEmptyString] = Field(default_factory=list)
    constraints: list[NonEmptyString] = Field(default_factory=list)
