import json
import sqlite3
from pathlib import Path

import pytest

from ops_agent.contracts import RuntimeStage, VerificationStatus
from ops_agent.integrations.timeout_retry_mvp import TimeoutRetryMvpCase


@pytest.mark.asyncio
async def test_timeout_retry_duplicate_create_real_mvp(tmp_path: Path) -> None:
    """One command owns setup, real execution, verification, persistence, and cleanup."""
    output_dir = tmp_path / "timeout-retry-case"
    case = TimeoutRetryMvpCase(output_dir=output_dir)

    outcome = await case.execute()

    assert outcome.setup_completed
    assert outcome.cleanup_completed
    assert outcome.final_state.runtime_stage is RuntimeStage.COMPLETED
    assert outcome.final_state.product is not None
    assert outcome.final_state.product.product_version == "2026.09-retry-enabled"
    assert outcome.loaded_skill_names == ["incident-analysis"]
    assert outcome.final_state.hypotheses is not None
    assert outcome.final_state.latest_evidence_plan is not None
    assert len(outcome.final_state.evidence) >= 6
    assert outcome.final_state.experiment_results
    assert outcome.final_state.experiment_results[-1].outputs["orders_created"] == 2
    assert outcome.final_state.verification_results[-1].status is VerificationStatus.CONFIRMED
    assert outcome.final_state.rca_report is not None

    evidence_by_id = {item.evidence_id: item for item in outcome.final_state.evidence}
    report_evidence_ids = {
        evidence_id
        for claim in (
            *outcome.final_state.rca_report.confirmed_facts,
            *outcome.final_state.rca_report.inferences,
        )
        for evidence_id in claim.evidence_ids
    }
    assert report_evidence_ids <= set(evidence_by_id)
    assert evidence_by_id["E-HTTP-REQUESTS"].structured_value == {
        "business_id": "BIZ-MVP-001",
        "request_count": 2,
    }
    assert evidence_by_id["E-DATABASE"].structured_value == {
        "business_id": "BIZ-MVP-001",
        "order_count": 2,
        "order_ids": [1, 2],
    }
    assert evidence_by_id["E-PAGE"].structured_value == {
        "events": ["submit", "timeout", "retry", "success"],
        "retry_count": 1,
    }

    request_rows = [
        json.loads(line)
        for line in outcome.artifacts.requests.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["request_id"] for row in request_rows] == ["HTTP-REQ-1", "HTTP-REQ-2"]
    assert len({row["trace_id"] for row in request_rows}) == 1
    assert request_rows[0]["created"] is True
    assert request_rows[0]["response_delay_ms"] > request_rows[0]["client_timeout_ms"]

    log_text = outcome.artifacts.logs.read_text(encoding="utf-8")
    assert "order_created" in log_text
    assert "HTTP-REQ-1" in log_text
    assert "HTTP-REQ-2" in log_text

    with sqlite3.connect(outcome.artifacts.database) as connection:
        orders = connection.execute("SELECT id, business_id FROM orders ORDER BY id").fetchall()
    assert orders == [(1, "BIZ-MVP-001"), (2, "BIZ-MVP-001")]

    page_events = json.loads(outcome.artifacts.page.read_text(encoding="utf-8"))
    assert page_events["events"] == ["submit", "timeout", "retry", "success"]
    assert '<form id="create-order">' in outcome.artifacts.html.read_text(encoding="utf-8")
    assert outcome.artifacts.experiment_result.is_file()
    assert outcome.artifacts.rca_report.is_file()
    assert outcome.artifacts.case_summary.is_file()
    assert not case.environment_active
