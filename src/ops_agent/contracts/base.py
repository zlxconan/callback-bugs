"""Shared fields and identifiers for public contract version 1."""

from typing import Annotated, Literal, TypeAlias

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

SchemaVersion: TypeAlias = Literal["1.0"]
IncidentId: TypeAlias = Annotated[str, Field(pattern=r"^INC-[A-Za-z0-9][A-Za-z0-9._-]*$")]
RequestId: TypeAlias = Annotated[str, Field(pattern=r"^REQ-[A-Za-z0-9][A-Za-z0-9._-]*$")]
HypothesisId: TypeAlias = Annotated[str, Field(pattern=r"^H-[A-Za-z0-9][A-Za-z0-9._-]*$")]
EvidenceId: TypeAlias = Annotated[str, Field(pattern=r"^E-[A-Za-z0-9][A-Za-z0-9._-]*$")]
ExperimentId: TypeAlias = Annotated[str, Field(pattern=r"^EXP-[A-Za-z0-9][A-Za-z0-9._-]*$")]
TaskId: TypeAlias = Annotated[str, Field(pattern=r"^TASK-[A-Za-z0-9][A-Za-z0-9._-]*$")]
AuditEventId: TypeAlias = Annotated[str, Field(pattern=r"^AUD-[A-Za-z0-9][A-Za-z0-9._-]*$")]
ReportId: TypeAlias = Annotated[str, Field(pattern=r"^RCA-[A-Za-z0-9][A-Za-z0-9._-]*$")]
Confidence: TypeAlias = Annotated[float, Field(ge=0.0, le=1.0)]
NonEmptyString: TypeAlias = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    """Base for nested values that reject undeclared fields."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class ContractBase(StrictModel):
    """Correlation and provenance fields carried by every public contract."""

    schema_version: SchemaVersion = "1.0"
    incident_id: IncidentId
    request_id: RequestId
    timestamp: AwareDatetime
    source: NonEmptyString
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class RawReference(StrictModel):
    """Stable reference to raw data kept outside a contract payload."""

    uri: NonEmptyString
    digest: str | None = None
    media_type: str | None = None


class TimeRange(StrictModel):
    """Inclusive UTC-aware time range used for evidence collection."""

    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def end_must_not_precede_start(self) -> "TimeRange":
        if self.end < self.start:
            raise ValueError("end must not precede start")
        return self
