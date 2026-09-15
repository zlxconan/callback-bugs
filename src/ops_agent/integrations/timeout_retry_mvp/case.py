"""One-command composition root for the timeout/retry MVP case."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ops_agent.contracts import (
    IncidentSeverity,
    IncidentState,
    ProblemContext,
    StartIncidentRequest,
    VerificationStatus,
)
from ops_agent.core.runtime import CoreRuntime, RuntimeConfig
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.local_agent import FakeIncidentRunner, FixedClock
from ops_agent.skills import SkillCatalog

from .adapters import (
    ArtifactInvestigationEngine,
    FixtureKnowledgeEngine,
    HttpSqliteReproductionEngine,
    MvpRuleReasoningEngine,
)
from .api.environment import TimeoutRetryEnvironment

NOW = datetime(2026, 9, 15, 8, 0, tzinfo=UTC)
PROJECT_ROOT = Path(__file__).parents[4]
KNOWLEDGE_FIXTURE = (
    PROJECT_ROOT / "examples" / "mvp" / "timeout-retry-duplicate-create" / "product-knowledge.json"
)
SKILLS_ROOT = PROJECT_ROOT / "skills"


class MvpArtifactPaths(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requests: Path
    logs: Path
    database: Path
    page: Path
    html: Path
    experiment_result: Path
    rca_report: Path
    case_summary: Path


class MvpCaseOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup_completed: bool
    cleanup_completed: bool
    loaded_skill_names: list[str]
    final_state: IncidentState
    artifacts: MvpArtifactPaths


class TimeoutRetryMvpCase:
    """Own setup -> incident capture -> Runtime run -> verify -> persist -> cleanup."""

    def __init__(self, *, output_dir: Path) -> None:
        self._environment = TimeoutRetryEnvironment(output_dir)
        self._setup_completed = False
        self._cleanup_completed = False

    @property
    def environment_active(self) -> bool:
        return self._environment.active

    async def setup(self) -> None:
        await self._environment.setup()
        self._setup_completed = True

    async def run(self) -> tuple[IncidentState, list[str]]:
        # Capture the reported incident using the same real backend before investigation.
        await self._environment.run_scenario()
        skill_names = ["product-knowledge", "troubleshooting"]
        catalog = SkillCatalog(SKILLS_ROOT)
        for name in skill_names:
            catalog.get(name)

        runner = FakeIncidentRunner(
            runtime=CoreRuntime(
                repository=InMemoryStateRepository(),
                clock=FixedClock(NOW),
                config=RuntimeConfig(
                    max_attempts=3,
                    task_timeout_seconds=30,
                    max_reflection_loops=2,
                ),
            ),
            knowledge=FixtureKnowledgeEngine(KNOWLEDGE_FIXTURE),
            reasoning=MvpRuleReasoningEngine(),
            investigation=ArtifactInvestigationEngine(self._environment),
            reproduction=HttpSqliteReproductionEngine(self._environment),
        )
        outcome = await runner.run(self._start_command())
        return outcome.final_state, skill_names

    async def verify(self, state: IncidentState) -> None:
        if state.rca_report is None:
            raise RuntimeError("MVP Runtime did not produce an RCA report")
        if not state.experiment_results or not state.verification_results:
            raise RuntimeError("MVP Runtime did not execute and verify an experiment")
        if state.experiment_results[-1].outputs.get("orders_created") != 2:
            raise RuntimeError("MVP did not reproduce two orders")
        if state.verification_results[-1].status is not VerificationStatus.CONFIRMED:
            raise RuntimeError("MVP duplicate-create verification was not confirmed")
        if len(self._environment.order_ids(TimeoutRetryEnvironment.BUSINESS_ID)) != 2:
            raise RuntimeError("SQLite verification did not find exactly two orders")

    async def cleanup(self) -> None:
        await self._environment.cleanup()
        self._cleanup_completed = True

    async def execute(self) -> MvpCaseOutcome:
        """Execute the complete lifecycle with cleanup guaranteed on failure."""
        state: IncidentState | None = None
        skill_names: list[str] = []
        try:
            await self.setup()
            state, skill_names = await self.run()
            await self.verify(state)
            artifacts = self._persist(state)
        finally:
            await self.cleanup()
        if state is None:
            raise RuntimeError("MVP case ended without IncidentState")
        return MvpCaseOutcome(
            setup_completed=self._setup_completed,
            cleanup_completed=self._cleanup_completed,
            loaded_skill_names=skill_names,
            final_state=state,
            artifacts=artifacts,
        )

    def _persist(self, state: IncidentState) -> MvpArtifactPaths:
        if state.rca_report is None or not state.experiment_results:
            raise RuntimeError("cannot persist an incomplete MVP case")
        experiment_path = self._environment.output_dir / "experiment-result.json"
        rca_path = self._environment.output_dir / "rca-report.json"
        summary_path = self._environment.output_dir / "case-summary.json"
        experiment_path.write_text(
            state.experiment_results[-1].model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        rca_path.write_text(state.rca_report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        summary = {
            "case": "timeout-retry-duplicate-create",
            "incident_id": state.incident_id,
            "product_version": state.product.product_version if state.product else None,
            "hypothesis": "H-1",
            "evidence_ids": [item.evidence_id for item in state.evidence],
            "experiment_id": state.experiment_results[-1].experiment_id,
            "verification": state.verification_results[-1].status,
            "root_cause": state.rca_report.root_causes[0].description,
            "unverified": [
                "Playwright 浏览器执行未验证。",
                "mitmproxy/Toxiproxy 外部网络故障注入未验证。",
                "生产环境真实延迟来源未验证。",
            ],
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return MvpArtifactPaths(
            requests=self._environment.requests_path,
            logs=self._environment.logs_path,
            database=self._environment.database_path,
            page=self._environment.page_path,
            html=self._environment.html_path,
            experiment_result=experiment_path,
            rca_report=rca_path,
            case_summary=summary_path,
        )

    @staticmethod
    def _start_command() -> StartIncidentRequest:
        problem = ProblemContext(
            schema_version="1.0",
            incident_id="INC-MVP-TIMEOUT-RETRY-001",
            request_id="REQ-MVP-TIMEOUT-RETRY-001",
            timestamp=NOW,
            source="timeout-retry-mvp",
            metadata={"case": "timeout-retry-duplicate-create"},
            title="创建订单首次响应超时，自动重试后产生重复订单",
            description="相同 business_id 的首次请求已成功，响应延迟触发重试并再次创建。",
            symptoms=["首次请求超时", "客户端自动重试", "相同业务标识出现两个订单"],
            severity=IncidentSeverity.HIGH,
            observed_at=NOW,
            affected_services=["order-api"],
            environment={"name": "isolated-mvp", "external_systems": False},
        )
        return StartIncidentRequest(
            schema_version=problem.schema_version,
            incident_id=problem.incident_id,
            request_id=problem.request_id,
            timestamp=problem.timestamp,
            source="timeout-retry-mvp",
            metadata={},
            problem=problem,
        )
