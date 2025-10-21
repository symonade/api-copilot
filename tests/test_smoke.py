# tests/test_smoke.py
import os
import pytest

from src.eval_harness import run_smoke, _is_up, API_REGISTRY

PRIMARY = os.getenv("PRIMARY_API_BASE_URL", "http://localhost:8000")
SECONDARY = os.getenv("SECONDARY_API_BASE_URL", "http://localhost:8001")


@pytest.mark.timeout(30)
def test_primary_smoke_only():
    assert _is_up(PRIMARY), (
        f"Primary API not running at {PRIMARY}. Start: python -m uvicorn src.mock_api:app --port 8000 --reload"
    )
    summary = run_smoke(include_scheduler=False)

    a = summary["assertions"]
    assert a["router_primary_for_auth"], "Auth should route to primary adapter"
    assert a["router_primary_for_cost"], "Cost flow should route to primary adapter"
    assert a["primary_health_ok"], "Primary health should be Operational"
    assert a["rag_auth_nonempty"], "RAG should return results for auth query"
    assert a["rag_cost_nonempty"], "RAG should return results for cost query"
    assert a["write_flow_ok"], "Create project + add cost items should succeed"


@pytest.mark.timeout(30)
def test_scheduler_optional():
    # If scheduler isn't up, we skip gracefully
    if not _is_up(SECONDARY):
        pytest.skip(
            "Scheduler API not running; start with: python -m uvicorn src.mock_api2:app --port 8001 --reload"
        )
    summary = run_smoke(include_scheduler=True)
    assert summary.get("scheduler_checked") is True, "Scheduler should be health-checked if running"

