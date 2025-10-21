# src/eval_harness.py
import os
from typing import Dict, Any, List, Tuple

import requests

# Reuse registry + tools (no LLM)
from src.apis import ApiRegistry, ContechApi, SchedulerApi
from src.tools import check_api_status, search_documentation, create_project as tool_create_project, add_cost_item as tool_add_cost_item

JSON = Dict[str, Any]

# ---- Registry bootstrap (same as agent) ----
API_REGISTRY = ApiRegistry()
API_REGISTRY.register(ContechApi())
API_REGISTRY.register(SchedulerApi())


def _is_up(url: str, timeout: float = 3.0) -> bool:
    url = url.rstrip("/") + "/status"
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def select_api_for(query: str) -> Tuple[str, str]:
    """Return (name, base_url) selected by registry for a given query."""
    adapter = API_REGISTRY.select_for_query(query)
    return adapter.name, adapter.base_url


def health(base_url: str) -> JSON:
    """Call the tool deterministically (no LLM)."""
    return check_api_status.invoke({"base_url": base_url})


def rag(query: str, api_hint: str = "", k: int = 4) -> List[JSON]:
    """Call RAG tool deterministically (no LLM)."""
    return search_documentation.invoke({"query": query, "k": k, "api_hint": api_hint})


# ---- Minimal helpers to hit the mock ConTech API (via our stable tools) ----
def create_project(base_url: str, name: str) -> JSON:
    # Use the real tool to ensure payload/auth compatibility with the mock
    result = tool_create_project.invoke({
        "payload": {"projectName": name, "clientId": "CUST-TEST"},
        "base_url": base_url,
        "headers": {},
        "timeout": 10,
    })
    if isinstance(result, dict) and result.get("ok"):
        data = result.get("data") or {}
        return data
    raise RuntimeError(f"create_project failed: {result}")


def add_cost_item(base_url: str, project_id: str, *, item_code: str, description: str, qty: float = 1.0, unit_cost: float = 10.0) -> JSON:
    result = tool_add_cost_item.invoke({
        "project_id": project_id,
        "item": {
            "itemCode": item_code,
            "description": description,
            "quantity": qty,
            "unitCost": unit_cost,
        },
        "base_url": base_url,
        "headers": {},
        "timeout": 10,
    })
    if isinstance(result, dict) and result.get("ok"):
        data = result.get("data") or {}
        return data
    raise RuntimeError(f"add_cost_item failed: {result}")


def run_smoke(include_scheduler: bool = True) -> JSON:
    """
    Deterministic smoke run:
      - router selection for typical queries
      - health check for selected API(s)
      - RAG presence check
      - create project + add two cost items
      - optional scheduler health if reachable
    Returns a summary dict (assert-able by tests).
    """
    summary: JSON = {"steps": [], "errors": []}

    # 1) Router selection checks
    sel_auth = select_api_for("How do I authenticate?")
    sel_cost = select_api_for("Create a project and add cost items.")
    sel_sched = select_api_for("Show the schedule timeline for project ABC")

    summary["steps"].append({"router_auth": sel_auth})
    summary["steps"].append({"router_cost": sel_cost})
    summary["steps"].append({"router_schedule": sel_sched})

    # 2) Health checks (primary is required)
    primary_name, primary_url = sel_auth  # both auth & cost should route to primary
    h_primary = health(primary_url)
    summary["steps"].append({"health_primary": h_primary})

    if include_scheduler:
        sched_name, sched_url = sel_sched
        if _is_up(sched_url):
            h_sched = health(sched_url)
            summary["steps"].append({"health_scheduler": h_sched})
            summary["scheduler_checked"] = True
        else:
            summary["steps"].append({"health_scheduler": "skipped - server not running"})
            summary["scheduler_checked"] = False

    # 3) RAG checks (just verify non-empty message-less results)
    rag_auth = rag("How do I authenticate to the API?", api_hint=primary_name)
    rag_cost = rag("Create a project and add some cost items.", api_hint=primary_name)

    summary["steps"].append({"rag_auth_count": len(rag_auth)})
    summary["steps"].append({"rag_cost_count": len(rag_cost)})

    # 4) Write path (create project + add costs) against primary
    try:
        new_proj = create_project(primary_url, "New Site Development")
        pid = new_proj.get("id") or new_proj.get("projectId")
        c1 = add_cost_item(primary_url, pid, item_code="LAB-ELEC-01", description="Electrician Hourly Rate", qty=2, unit_cost=50)
        c2 = add_cost_item(primary_url, pid, item_code="MAT-CONC-01", description="Concrete (yard)", qty=5, unit_cost=120)
        summary["steps"].append({"create_project_id": pid})
        summary["steps"].append({"add_cost_1": c1})
        summary["steps"].append({"add_cost_2": c2})
        summary["write_flow_ok"] = True
    except Exception as e:
        summary["errors"].append(f"write_flow_failed: {e}")
        summary["write_flow_ok"] = False

    # Quick booleans the test can assert
    summary["assertions"] = {
        "router_primary_for_auth": sel_auth[0] != "scheduler",
        "router_primary_for_cost": sel_cost[0] != "scheduler",
        "primary_health_ok": (h_primary.get("status") == "Operational"),
        "rag_auth_nonempty": (isinstance(rag_auth, list) and len(rag_auth) > 0),
        "rag_cost_nonempty": (isinstance(rag_cost, list) and len(rag_cost) > 0),
        "write_flow_ok": summary["write_flow_ok"],
    }
    return summary

