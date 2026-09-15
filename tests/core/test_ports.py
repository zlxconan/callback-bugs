import inspect
from pathlib import Path
from typing import Any, get_type_hints

import pytest

from ops_agent.contracts import (
    AuditEvent,
    CleanupResult,
    EnvironmentCleanupRequest,
    Evidence,
    EvidenceBatch,
    EvidencePlan,
    EvidencePlanningRequest,
    EvidenceRequest,
    ExperimentExecutionRequest,
    ExperimentPlan,
    ExperimentPlanningRequest,
    ExperimentResult,
    ExperimentVerificationRequest,
    FinishIncidentRequest,
    HypothesisGenerationRequest,
    HypothesisSet,
    IncidentQuery,
    IncidentState,
    KnowledgeContext,
    KnowledgeQuery,
    PreparedEnvironment,
    ProblemContext,
    ProductContext,
    RCAReport,
    ReflectionRequest,
    ReflectionResult,
    RootCauseAssessment,
    RootCauseVerificationRequest,
    RuntimeTask,
    StartIncidentRequest,
    TaskResult,
    TroubleshootingContext,
    VerificationResult,
)
from ops_agent.ports import (
    ApiToolPort,
    BrowserToolPort,
    ChangeToolPort,
    ClockPort,
    CodeGraphToolPort,
    FaultInjectionToolPort,
    InvestigationPort,
    K8sToolPort,
    KnowledgePort,
    LogToolPort,
    MetricToolPort,
    ReasoningPort,
    ReproductionPort,
    RuntimePort,
    ShellToolPort,
    StateRepositoryPort,
    TopologyToolPort,
    TraceToolPort,
)

EXAMPLES = Path(__file__).parents[2] / "examples" / "contracts"


def load_example(model: type[Any], filename: str) -> Any:
    return model.model_validate_json((EXAMPLES / filename).read_text(encoding="utf-8"))


PORT_METHODS: dict[type[Any], set[str]] = {
    RuntimePort: {
        "start_incident",
        "get_next_task",
        "submit_task_result",
        "get_state",
        "finish_incident",
    },
    KnowledgePort: {
        "resolve_product",
        "query_product_knowledge",
        "query_troubleshooting",
    },
    ReasoningPort: {
        "generate_hypotheses",
        "plan_evidence",
        "reflect",
        "verify_root_cause",
        "plan_experiment",
    },
    InvestigationPort: {"collect", "collect_batch"},
    ReproductionPort: {"prepare", "execute", "verify", "cleanup"},
    StateRepositoryPort: {"create", "get", "save", "list_events", "append_event"},
    ClockPort: {"now"},
    TraceToolPort: {"collect"},
    LogToolPort: {"collect"},
    MetricToolPort: {"collect"},
    K8sToolPort: {"collect"},
    ChangeToolPort: {"collect"},
    TopologyToolPort: {"collect"},
    CodeGraphToolPort: {"collect"},
    BrowserToolPort: {"execute"},
    ApiToolPort: {"execute"},
    ShellToolPort: {"execute"},
    FaultInjectionToolPort: {"apply", "rollback"},
}


@pytest.mark.parametrize(("port", "methods"), PORT_METHODS.items())
def test_port_exists_as_runtime_checkable_protocol(
    port: type[Any],
    methods: set[str],
) -> None:
    assert getattr(port, "_is_protocol", False)
    assert getattr(port, "_is_runtime_protocol", False)
    assert methods.issubset(set(port.__dict__))


@pytest.mark.parametrize(("port", "methods"), PORT_METHODS.items())
def test_every_port_method_is_async_and_strongly_typed(
    port: type[Any],
    methods: set[str],
) -> None:
    for method_name in methods:
        method = getattr(port, method_name)
        hints = get_type_hints(method)

        assert inspect.iscoroutinefunction(method)
        assert "return" in hints
        assert Any not in hints.values()
        assert dict not in hints.values()
        assert all("fastapi" not in str(value) for value in hints.values())
        assert all("langchain" not in str(value) for value in hints.values())


class FakeKnowledgePort:
    def __init__(
        self,
        product: ProductContext,
        knowledge: KnowledgeContext,
        troubleshooting: TroubleshootingContext,
    ) -> None:
        self.product = product
        self.knowledge = knowledge
        self.troubleshooting = troubleshooting

    async def resolve_product(self, problem: ProblemContext) -> ProductContext:
        return self.product

    async def query_product_knowledge(self, query: KnowledgeQuery) -> KnowledgeContext:
        return self.knowledge

    async def query_troubleshooting(self, query: KnowledgeQuery) -> TroubleshootingContext:
        return self.troubleshooting


class FakeRuntimePort:
    def __init__(
        self,
        state: IncidentState,
        task: RuntimeTask,
        report: RCAReport,
    ) -> None:
        self.state = state
        self.task = task
        self.report = report

    async def start_incident(self, command: StartIncidentRequest) -> IncidentState:
        return self.state

    async def get_next_task(self, query: IncidentQuery) -> RuntimeTask | None:
        return self.task

    async def submit_task_result(self, result: TaskResult) -> IncidentState:
        return self.state

    async def get_state(self, query: IncidentQuery) -> IncidentState:
        return self.state

    async def finish_incident(self, command: FinishIncidentRequest) -> RCAReport:
        return self.report


class FakeReasoningPort:
    def __init__(
        self,
        hypotheses: HypothesisSet,
        evidence_plan: EvidencePlan,
        reflection: ReflectionResult,
        assessment: RootCauseAssessment,
        experiment_plan: ExperimentPlan,
    ) -> None:
        self.hypotheses = hypotheses
        self.evidence_plan = evidence_plan
        self.reflection = reflection
        self.assessment = assessment
        self.experiment_plan = experiment_plan

    async def generate_hypotheses(self, request: HypothesisGenerationRequest) -> HypothesisSet:
        return self.hypotheses

    async def plan_evidence(self, request: EvidencePlanningRequest) -> EvidencePlan:
        return self.evidence_plan

    async def reflect(self, request: ReflectionRequest) -> ReflectionResult:
        return self.reflection

    async def verify_root_cause(self, request: RootCauseVerificationRequest) -> RootCauseAssessment:
        return self.assessment

    async def plan_experiment(self, request: ExperimentPlanningRequest) -> ExperimentPlan:
        return self.experiment_plan


class FakeInvestigationPort:
    def __init__(self, item: Evidence) -> None:
        self.item = item

    async def collect(self, request: EvidenceRequest) -> Evidence:
        return self.item

    async def collect_batch(self, plan: EvidencePlan) -> EvidenceBatch:
        return EvidenceBatch(
            schema_version=plan.schema_version,
            incident_id=plan.incident_id,
            request_id=plan.request_id,
            timestamp=plan.timestamp,
            source="fake-investigation",
            metadata={},
            evidence=[self.item],
        )


class FakeReproductionPort:
    def __init__(
        self,
        prepared: PreparedEnvironment,
        result: ExperimentResult,
        verification: VerificationResult,
        cleanup: CleanupResult,
    ) -> None:
        self.prepared = prepared
        self.result = result
        self.verification = verification
        self.cleanup_result = cleanup

    async def prepare(self, plan: ExperimentPlan) -> PreparedEnvironment:
        return self.prepared

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        return self.result

    async def verify(self, request: ExperimentVerificationRequest) -> VerificationResult:
        return self.verification

    async def cleanup(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        return self.cleanup_result


class FakeStateRepository:
    def __init__(self) -> None:
        self.state: IncidentState | None = None

    async def create(self, state: IncidentState) -> IncidentState:
        self.state = state
        return state

    async def get(self, query: IncidentQuery) -> IncidentState | None:
        return self.state

    async def save(self, state: IncidentState) -> IncidentState:
        self.state = state
        return state

    async def list_events(self, query: IncidentQuery) -> tuple[AuditEvent, ...]:
        return ()

    async def append_event(self, event: AuditEvent) -> AuditEvent:
        return event


class FakeEvidenceTool:
    def __init__(self, item: Evidence) -> None:
        self.item = item

    async def collect(self, request: EvidenceRequest) -> Evidence:
        return self.item


class FakeExecutionTool:
    def __init__(self, result: ExperimentResult) -> None:
        self.result = result

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        return self.result


class FakeFaultInjectionTool:
    def __init__(self, result: ExperimentResult, cleanup: CleanupResult) -> None:
        self.result = result
        self.cleanup_result = cleanup

    async def apply(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        return self.result

    async def rollback(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        return self.cleanup_result


@pytest.mark.asyncio
async def test_fake_engine_and_repository_ports_are_compatible() -> None:
    problem = load_example(ProblemContext, "problem-context.json")
    product = load_example(ProductContext, "product-context.json")
    knowledge = load_example(KnowledgeContext, "knowledge-context.json")
    troubleshooting = load_example(TroubleshootingContext, "troubleshooting-context.json")
    item = load_example(Evidence, "evidence.json")
    plan = load_example(EvidencePlan, "evidence-plan.json")
    query = KnowledgeQuery(
        **problem.model_dump(
            include={
                "schema_version",
                "incident_id",
                "request_id",
                "timestamp",
                "source",
                "metadata",
            }
        ),
        problem=problem,
        product=product,
        query="Expected behavior",
    )

    knowledge_port: KnowledgePort = FakeKnowledgePort(product, knowledge, troubleshooting)
    investigation_port: InvestigationPort = FakeInvestigationPort(item)
    repository: StateRepositoryPort = FakeStateRepository()

    assert isinstance(knowledge_port, KnowledgePort)
    assert isinstance(investigation_port, InvestigationPort)
    assert isinstance(repository, StateRepositoryPort)
    assert await knowledge_port.resolve_product(problem) == product
    assert await knowledge_port.query_product_knowledge(query) == knowledge
    assert (await investigation_port.collect_batch(plan)).evidence == [item]


def test_all_engine_level_protocols_accept_deterministic_fakes() -> None:
    state = load_example(IncidentState, "incident-state.json")
    task = load_example(RuntimeTask, "runtime-task.json")
    report = load_example(RCAReport, "rca-report.json")
    hypotheses = load_example(HypothesisSet, "hypothesis-set.json")
    evidence_plan = load_example(EvidencePlan, "evidence-plan.json")
    reflection = load_example(ReflectionResult, "reflection-result.json")
    assessment = load_example(RootCauseAssessment, "root-cause-assessment.json")
    experiment_plan = load_example(ExperimentPlan, "experiment-plan.json")
    experiment_result = load_example(ExperimentResult, "experiment-result.json")
    verification = load_example(VerificationResult, "verification-result.json")
    prepared = PreparedEnvironment(
        schema_version="1.0",
        incident_id=state.incident_id,
        request_id=state.request_id,
        timestamp=state.timestamp,
        source="fake-reproduction",
        metadata={},
        experiment_id=experiment_plan.experiment_id,
        environment_ref="ENV-1001",
        ready=True,
        expires_at=None,
    )
    cleanup = CleanupResult(
        schema_version="1.0",
        incident_id=state.incident_id,
        request_id=state.request_id,
        timestamp=state.timestamp,
        source="fake-reproduction",
        metadata={},
        experiment_id=experiment_plan.experiment_id,
        environment_ref=prepared.environment_ref,
        cleaned=True,
        observations=[],
    )

    runtime: RuntimePort = FakeRuntimePort(state, task, report)
    reasoning: ReasoningPort = FakeReasoningPort(
        hypotheses,
        evidence_plan,
        reflection,
        assessment,
        experiment_plan,
    )
    reproduction: ReproductionPort = FakeReproductionPort(
        prepared,
        experiment_result,
        verification,
        cleanup,
    )

    assert isinstance(runtime, RuntimePort)
    assert isinstance(reasoning, ReasoningPort)
    assert isinstance(reproduction, ReproductionPort)


@pytest.mark.asyncio
async def test_fake_tool_ports_are_structurally_compatible() -> None:
    item = load_example(Evidence, "evidence.json")
    request = load_example(EvidenceRequest, "evidence-request.json")
    plan = load_example(ExperimentPlan, "experiment-plan.json")
    result = load_example(ExperimentResult, "experiment-result.json")
    prepared = PreparedEnvironment(
        schema_version="1.0",
        incident_id=plan.incident_id,
        request_id=plan.request_id,
        timestamp=plan.timestamp,
        source="fake-reproduction",
        metadata={},
        experiment_id=plan.experiment_id,
        environment_ref="ENV-1001",
        ready=True,
        expires_at=None,
    )
    execution = ExperimentExecutionRequest(
        schema_version="1.0",
        incident_id=plan.incident_id,
        request_id=plan.request_id,
        timestamp=plan.timestamp,
        source="runtime",
        metadata={},
        plan=plan,
        environment=prepared,
    )
    cleanup = CleanupResult(
        schema_version="1.0",
        incident_id=plan.incident_id,
        request_id=plan.request_id,
        timestamp=plan.timestamp,
        source="fake-reproduction",
        metadata={},
        experiment_id=plan.experiment_id,
        environment_ref=prepared.environment_ref,
        cleaned=True,
        observations=[],
    )

    evidence_tools: tuple[
        TraceToolPort
        | LogToolPort
        | MetricToolPort
        | K8sToolPort
        | ChangeToolPort
        | TopologyToolPort
        | CodeGraphToolPort,
        ...,
    ] = tuple(FakeEvidenceTool(item) for _ in range(7))
    execution_tools: tuple[BrowserToolPort | ApiToolPort | ShellToolPort, ...] = tuple(
        FakeExecutionTool(result) for _ in range(3)
    )
    fault_tool: FaultInjectionToolPort = FakeFaultInjectionTool(result, cleanup)

    collected = [await tool.collect(request) for tool in evidence_tools]
    executed = [await tool.execute(execution) for tool in execution_tools]

    assert collected == [item] * 7
    assert executed == [result] * 3
    assert await fault_tool.apply(execution) == result
