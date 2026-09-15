"""Audit trail contract."""

from pydantic import Field, JsonValue

from ops_agent.contracts.base import AuditEventId, ContractBase, NonEmptyString


class AuditEvent(ContractBase):
    """Immutable description of an actor action and its outcome."""

    audit_event_id: AuditEventId
    event_type: NonEmptyString
    actor: NonEmptyString
    action: NonEmptyString
    outcome: NonEmptyString
    target_ref: NonEmptyString
    details: dict[str, JsonValue] = Field(default_factory=dict)
    previous_event_id: AuditEventId | None = None
