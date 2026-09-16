"""Shared RuntimeTask to Canonical Skill routing."""

from ops_agent.contracts import RuntimeStage, RuntimeTask
from ops_agent.skills.catalog import SkillCatalog
from ops_agent.skills.models import CanonicalSkill


class RuntimeTaskSkillRouter:
    """Explicit Runtime Stage to Canonical Skill mapping shared by Agent Hosts."""

    _MAPPING: dict[RuntimeStage, tuple[str, ...]] = {
        RuntimeStage.NORMALIZE: ("incident-analysis",),
        RuntimeStage.KNOWLEDGE_LOOKUP: ("incident-analysis",),
        RuntimeStage.HYPOTHESIS: ("hypothesis-generation",),
        RuntimeStage.EVIDENCE_PLAN: ("evidence-planning",),
        RuntimeStage.INVESTIGATE: ("incident-analysis",),
        RuntimeStage.ROOT_CAUSE_ASSESSMENT: ("incident-analysis",),
        RuntimeStage.EXPERIMENT_PLAN: ("reproduction-planning",),
        RuntimeStage.REPRODUCE: ("incident-analysis",),
        RuntimeStage.VERIFY: ("incident-analysis",),
        RuntimeStage.REFLECT: ("reflection",),
        RuntimeStage.RCA: ("rca-report",),
        RuntimeStage.WAITING_HUMAN: ("incident-analysis",),
    }

    def __init__(self, catalog: SkillCatalog) -> None:
        self._catalog = catalog

    def names_for(self, stage: RuntimeStage) -> tuple[str, ...]:
        try:
            return self._MAPPING[stage]
        except KeyError as error:
            raise ValueError(f"No Canonical Skill mapping for Runtime Stage: {stage}") from error

    def resolve(self, task: RuntimeTask) -> tuple[CanonicalSkill, ...]:
        if task.stage is None:
            raise ValueError(f"RuntimeTask has no Stage: {task.task_id}")
        return tuple(self._catalog.get(name) for name in self.names_for(task.stage))
