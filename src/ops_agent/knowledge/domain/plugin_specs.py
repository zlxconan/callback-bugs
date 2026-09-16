"""Internal schemas for Product and Troubleshooting Skill payloads."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

NonEmptyString = Annotated[str, Field(min_length=1)]


class PluginPayload(BaseModel):
    """Strict base for plugin-owned data that never crosses KnowledgePort."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ProductContextSpec(PluginPayload):
    product_name: NonEmptyString
    product_version: NonEmptyString
    component: NonEmptyString
    deployment_environment: NonEmptyString
    expected_behavior: NonEmptyString
    configuration: dict[str, JsonValue] = Field(default_factory=dict)


class ProductFeatureSpec(PluginPayload):
    id: NonEmptyString
    description: NonEmptyString


class RetryBehaviorSpec(PluginPayload):
    enabled: bool
    max_retries: int = Field(ge=0)
    description: NonEmptyString


class KnownIssueSpec(PluginPayload):
    id: NonEmptyString
    description: NonEmptyString


class ProductSkillSpec(PluginPayload):
    """Validated content of one PRODUCT plugin entrypoint."""

    schema_version: Literal["1.0"] = "1.0"
    product_context: ProductContextSpec
    features: tuple[ProductFeatureSpec, ...] = Field(min_length=1)
    retry_behavior: RetryBehaviorSpec
    known_issues: tuple[KnownIssueSpec, ...] = ()
    limitations: tuple[NonEmptyString, ...] = ()


class TroubleshootingFaultSpec(PluginPayload):
    id: NonEmptyString
    symptoms: tuple[NonEmptyString, ...] = Field(min_length=1)
    possible_causes: tuple[NonEmptyString, ...] = Field(min_length=1)
    recommended_actions: tuple[NonEmptyString, ...] = Field(min_length=1)
    validation_steps: tuple[NonEmptyString, ...] = Field(min_length=1)
    known_workarounds: tuple[NonEmptyString, ...] = ()
    constraints: tuple[NonEmptyString, ...] = ()


class TroubleshootingSkillSpec(PluginPayload):
    """Validated content of one TROUBLESHOOTING plugin entrypoint."""

    schema_version: Literal["1.0"] = "1.0"
    product: NonEmptyString
    product_versions: tuple[NonEmptyString, ...] = Field(min_length=1)
    faults: tuple[TroubleshootingFaultSpec, ...] = Field(min_length=1)
