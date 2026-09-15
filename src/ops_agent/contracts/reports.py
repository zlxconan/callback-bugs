"""Root-cause analysis report contract."""

from typing import Annotated

from pydantic import Field

from ops_agent.contracts.analysis import EvidenceBackedClaim, RootCause
from ops_agent.contracts.base import (
    ContractBase,
    EvidenceId,
    NonEmptyString,
    ReportId,
    StrictModel,
)
from ops_agent.contracts.enums import EvidenceRelationship

EvidenceChainTarget = Annotated[
    str,
    Field(pattern=r"^(H|E|EXP|RCA)-[A-Za-z0-9][A-Za-z0-9._-]*$"),
]


class RemediationRecommendation(StrictModel):
    """Prioritized corrective or preventive action."""

    action: NonEmptyString
    rationale: NonEmptyString
    priority: int = Field(ge=1, le=5)


class EvidenceChainLink(StrictModel):
    """A typed edge in the report's evidence chain."""

    evidence_id: EvidenceId
    relationship: EvidenceRelationship
    target_id: EvidenceChainTarget


class RCAReport(ContractBase):
    """Final report with facts, inferences, causes, actions, and gaps kept separate."""

    report_id: ReportId
    title: NonEmptyString
    executive_summary: NonEmptyString
    confirmed_facts: list[EvidenceBackedClaim] = Field(min_length=1)
    inferences: list[EvidenceBackedClaim] = Field(default_factory=list)
    root_causes: list[RootCause] = Field(min_length=1)
    remediation_recommendations: list[RemediationRecommendation] = Field(default_factory=list)
    unverified_items: list[NonEmptyString] = Field(default_factory=list)
    evidence_chain: list[EvidenceChainLink] = Field(min_length=1)
