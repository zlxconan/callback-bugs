"""Safety rules applied before an experiment obtains any resources."""

from ops_agent.contracts import ExperimentPlan
from ops_agent.reproduction.domain.config import ReproductionConfig
from ops_agent.reproduction.domain.errors import ReproductionPolicyError


class ReproductionEnvironmentPolicy:
    """Allow only explicitly isolated environment kinds in the first real engine."""

    def __init__(self, config: ReproductionConfig) -> None:
        self._allowed = frozenset(item.casefold() for item in config.allowed_environment_kinds)

    def validate(self, plan: ExperimentPlan) -> None:
        raw_kind = plan.environment.get("kind")
        if not isinstance(raw_kind, str) or not raw_kind.strip():
            raise ReproductionPolicyError("experiment environment.kind is required")
        kind = raw_kind.casefold()
        if kind == "production" or kind not in self._allowed:
            raise ReproductionPolicyError(
                f"environment {raw_kind!r} is not allowed; production write and fault "
                "injection are disabled"
            )
        if plan.environment.get("external_systems") is True:
            raise ReproductionPolicyError("experiments against external systems are not allowed")
