"""Stable enumerations used by public contract version 1."""

from enum import StrEnum


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HypothesisStatus(StrEnum):
    PROPOSED = "proposed"
    TESTING = "testing"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class EvidenceType(StrEnum):
    LOG = "log"
    METRIC = "metric"
    TRACE = "trace"
    EVENT = "event"
    CONFIGURATION = "configuration"
    CODE = "code"
    CHANGE = "change"
    USER_REPORT = "user_report"
    EXPERIMENT = "experiment"
    OTHER = "other"


class EvidenceAcquisitionStatus(StrEnum):
    REQUESTED = "requested"
    COLLECTING = "collecting"
    ACQUIRED = "acquired"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class ExperimentStatus(StrEnum):
    PLANNED = "planned"
    APPROVED = "approved"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VerificationStatus(StrEnum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class NextAction(StrEnum):
    COLLECT_EVIDENCE = "collect_evidence"
    REVISE_HYPOTHESES = "revise_hypotheses"
    PLAN_EXPERIMENT = "plan_experiment"
    ASSESS_ROOT_CAUSE = "assess_root_cause"
    REQUEST_HUMAN_INPUT = "request_human_input"
    STOP = "stop"


class RootCauseStatus(StrEnum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    UNKNOWN = "unknown"


class IncidentLifecycleStatus(StrEnum):
    RECEIVED = "received"
    CONTEXTUALIZING = "contextualizing"
    PLANNING = "planning"
    INVESTIGATING = "investigating"
    REFLECTING = "reflecting"
    REPRODUCTION_PLANNING = "reproduction_planning"
    WAITING_APPROVAL = "waiting_approval"
    REPRODUCING = "reproducing"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RuntimeStage(StrEnum):
    CREATED = "created"
    NORMALIZE = "normalize"
    KNOWLEDGE_LOOKUP = "knowledge_lookup"
    HYPOTHESIS = "hypothesis"
    EVIDENCE_PLAN = "evidence_plan"
    INVESTIGATE = "investigate"
    ROOT_CAUSE_ASSESSMENT = "root_cause_assessment"
    EXPERIMENT_PLAN = "experiment_plan"
    REPRODUCE = "reproduce"
    VERIFY = "verify"
    REFLECT = "reflect"
    RCA = "rca"
    PERSIST = "persist"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskKind(StrEnum):
    NORMALIZATION = "normalization"
    KNOWLEDGE = "knowledge"
    REASONING = "reasoning"
    INVESTIGATION = "investigation"
    REPRODUCTION = "reproduction"
    VERIFICATION = "verification"
    REFLECTION = "reflection"
    HUMAN_APPROVAL = "human_approval"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    POLICY = "policy"
    TRANSIENT = "transient"
    TIMEOUT = "timeout"
    DEPENDENCY = "dependency"
    USER_ACTION_REQUIRED = "user_action_required"
    TERMINAL = "terminal"


class EvidenceRelationship(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
