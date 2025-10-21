# src/agent.py
import os
import sys
import json
import re
from typing import Any, Dict, List, Optional, TypedDict

from dotenv import load_dotenv
from pathlib import Path
import logging

# --- Load environment ---------------------------------------------------------
# .env is one level up from /src
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=dotenv_path)

# --- CLI features banner (env-gated) -----------------------------------------
def _print_features_banner():
    if os.getenv("SHOW_FEATURES", "0") != "1":
        return
    try:
        rp = Path(__file__).resolve().parents[1] / "product" / "roadmap.json"
        data = json.loads(rp.read_text(encoding="utf-8"))
        bullets = [f"- {i['title']}" for i in data.get("next", [])[:3]]
        if bullets:
            print("\n=== Features Coming Soon ===")
            for b in bullets:
                print(b)
            print("===========================\n")
    except Exception:
        pass

_print_features_banner()

# --- Reduce noisy logs in production -----------------------------------------
if os.getenv("ENV", "dev").lower() == "prod":
    try:
        logging.getLogger("grpc").setLevel(logging.WARN)
        logging.getLogger("absl").setLevel(logging.WARN)
    except Exception:
        pass

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").strip()
print(f"API_BASE_URL resolved at startup: {API_BASE_URL}")

# LLM configuration with fallback + caps
PRIMARY_MODEL = os.getenv("LLM_MODEL_PRIMARY", os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")).strip()
FALLBACK_MODEL = os.getenv("LLM_MODEL_FALLBACK", "gemini-1.5-flash").strip()
try:
    MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "512"))
except ValueError:
    MAX_OUTPUT_TOKENS = 512

# --- Imports that depend on installed versions --------------------------------
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

# Tools (LangChain @tool objects)
# We support both `get_tools()` presence and direct imports for robustness.
search_documentation = None
check_api_status = None
create_project = None
add_cost_item = None
try:
    from src.tools import get_tools  # if available
    tools_list = get_tools()
    # Expect tools named exactly as in your tools.py
    for t in tools_list:
        tname = getattr(t, "name", "")
        if tname == "search_documentation":
            search_documentation = t
        if tname == "check_api_status":
            check_api_status = t
        if tname == "create_project":
            create_project = t
        if tname == "add_cost_item":
            add_cost_item = t
    print("src.tools loaded via get_tools().")
except Exception as e:
    try:
        from src.tools import (
            search_documentation as _sd,
            check_api_status as _hc,
            create_project as _cp,
            add_cost_item as _aci,
        )
        search_documentation = _sd
        check_api_status = _hc
        create_project = _cp
        add_cost_item = _aci
        print("src.tools loaded via direct imports.")
    except Exception as e2:
        print(f"WARNING: could not import tools: {e2}")

if search_documentation is None or check_api_status is None:
    print("WARNING: One or more tools are missing; RAG and health checks will be skipped.")

# --- API registry and selection ----------------------------------------------
from src.apis import ApiRegistry, ContechApi, SchedulerApi

API_REGISTRY = ApiRegistry()
API_REGISTRY.register(ContechApi())
API_REGISTRY.register(SchedulerApi())

def choose_api_for_query(user_query: str):
    adapter = API_REGISTRY.select_for_query(user_query)
    print(f"[Router] Selected API -> {adapter.name} ({adapter.base_url})")
    return adapter

# --- Safe LLM init with fallback ----------------------------------------------
def _init_llm(model_name: str) -> ChatGoogleGenerativeAI:
    print(f"Attempting to initialize LLM with model: {model_name}")
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.2,
    )
    print(f"LLM initialized successfully with model: {model_name} (max_output_tokens={MAX_OUTPUT_TOKENS})")
    return llm

def init_llm_with_fallback() -> ChatGoogleGenerativeAI:
    try:
        return _init_llm(PRIMARY_MODEL)
    except Exception as e:
        print(f"Primary model '{PRIMARY_MODEL}' failed: {e}. Falling back to '{FALLBACK_MODEL}'")
        return _init_llm(FALLBACK_MODEL)

llm = init_llm_with_fallback()

# --- Graph state ---------------------------------------------------------------
class AgentState(TypedDict, total=False):
    user_query: str
    api_status: Dict[str, Any]
    docs: List[Dict[str, Any]]
    plan: List[Dict[str, Any]]
    answer: str
    pm_score: Dict[str, Any]
    route: str
    events: List[str]
    # Block 7 execution results
    created_project: Dict[str, Any]
    project_id: str
    added_items: List[Dict[str, Any]]

def _append_event(state: AgentState, name: str) -> None:
    if "events" not in state or not isinstance(state["events"], list):
        state["events"] = []
    state["events"].append(name)

# --- Nodes --------------------------------------------------------------------

def health_check_node(state: AgentState) -> AgentState:
    """If the query mentions status/503/etc, run the health tool with API_BASE_URL."""
    _append_event(state, "health_check")
    query = (state.get("user_query") or "").lower()

    # Heuristic: run health check for status/5xx keywords
    should_check = any(k in query for k in ["status", "503", "502", "500", "timeout", "down", "health"]) or \
                   any(k in query for k in ["schedule", "calendar", "timeline", "deadline"])
    if not should_check:
        state["api_status"] = {"status": "skipped"}
        return state

    if check_api_status is None:
        state["api_status"] = {"status": "skipped", "details": "health tool unavailable"}
        return state

    try:
        adapter = choose_api_for_query(query)
        state["selected_api"] = {"name": adapter.name, "base_url": adapter.base_url}
        print(f"Performing API health check using tool... base_url={adapter.base_url}")
        # IMPORTANT: call tools via .invoke({...})
        resp = check_api_status.invoke({"base_url": adapter.base_url})
        # Some tool wrappers return strings; normalise to dict
        state["api_status"] = resp if isinstance(resp, dict) else {"status": "unknown", "raw": str(resp)}
    except Exception as e:
        print(f"Health check failed: {e}")
        state["api_status"] = {"status": "error", "details": str(e)}
    return state


def router_node(state: AgentState) -> AgentState:
    """Decide next action. Always return dict with a 'route' key."""
    _append_event(state, "router")
    q = (state.get("user_query") or "").lower()
    api_status = (state.get("api_status") or {}).get("status", "skipped")

    # Log selected API when routing (if not already logged in health check)
    try:
        sel = state.get("selected_api")
        if not sel:
            adapter = choose_api_for_query(q)
            state["selected_api"] = {"name": adapter.name, "base_url": adapter.base_url}
    except Exception:
        pass

    # If user asks status and we have a known status -> synthesizer
    if "status" in q and api_status in {"Operational", "Unavailable", "Unreachable", "error"}:
        route = "synthesizer"
    # Multi-step intents
    elif any(w in q for w in ["create a project", "add cost", "workflow", "sequence", "steps", "multi-step"]):
        route = "planner"
    # Auth or specific lookup → executor
    elif any(w in q for w in ["auth", "authenticate", "token", "api key", "503", "error"]):
        route = "executor"
    else:
        route = "synthesizer"

    state["route"] = route
    return state


def planner_node(state: AgentState) -> AgentState:
    """Produce a simple deterministic plan to keep it reliable and quota-friendly."""
    _append_event(state, "planner")
    q = (state.get("user_query") or "").lower()
    plan: List[Dict[str, Any]] = []

    if "create a project" in q and "cost" in q:
        plan = [
            {"order": 1, "description": "Create a project via POST /projects."},
            {"order": 2, "description": "Add cost items via POST /projects/{projectId}/cost-items."},
        ]
    elif "auth" in q or "authenticate" in q or "api key" in q or "token" in q:
        plan = [
            {"order": 1, "description": "Obtain API Key from Developer Portal."},
            {"order": 2, "description": "Send requests with X-API-Key header."},
        ]
    else:
        # Fallback: single-step "look it up"
        plan = [{"order": 1, "description": "Look up relevant endpoints in the docs."}]

    state["plan"] = plan
    return state


def executor_node(state: AgentState) -> AgentState:
    """Run a RAG lookup using search_documentation tool and stash results."""
    _append_event(state, "executor")
    if search_documentation is None:
        state["docs"] = []
        return state

    query = state.get("user_query") or ""
    # Derive API hint from selection
    api_hint = ""
    sel = state.get("selected_api") or {}
    if isinstance(sel, dict):
        api_hint = sel.get("name") or ""
    try:
        print("\n--- Running RAG Search ---")
        print(f"Query: {query}")
        # IMPORTANT: call tools via .invoke({...})
        payload = {"query": query, "k": 4}
        if api_hint:
            payload["api_hint"] = api_hint
        results = search_documentation.invoke(payload)
        # Normalise return to a list of dicts
        if isinstance(results, list):
            state["docs"] = results
        elif isinstance(results, dict):
            state["docs"] = [results]
        else:
            state["docs"] = [{"message": str(results)}]

        # Execute real actions for the specific workflow (Block 7)
        uq = query.lower()
        if (
            ("create a project" in uq and "cost" in uq)
            and create_project is not None
            and add_cost_item is not None
        ):
            try:
                adapter = choose_api_for_query(query)
            except Exception:
                adapter = None
            if adapter is not None:
                # Optional health check before performing actions
                try:
                    _ = check_api_status.invoke({"base_url": adapter.base_url}) if check_api_status else None
                except Exception:
                    pass

                project_payload = {"projectName": "New Site Development", "clientId": "CUST-456"}
                cp = create_project.invoke({
                    "payload": project_payload,
                    "base_url": adapter.base_url,
                    "headers": adapter.auth_headers() if hasattr(adapter, "auth_headers") else {},
                    "timeout": 10,
                })

                project_id = None
                if isinstance(cp, dict) and cp.get("ok") and isinstance(cp.get("data"), dict):
                    data = cp["data"]
                    project_id = data.get("projectId") or data.get("id")

                cost_results = []
                if project_id:
                    items = [
                        {"itemCode": "LAB-ELEC-01", "description": "Electrician Hourly Rate", "quantity": 8, "unitCost": 65},
                        {"itemCode": "MAT-CONC-2Y", "description": "Concrete (2yd)", "quantity": 1, "unitCost": 240},
                    ]
                    for item in items:
                        res = add_cost_item.invoke({
                            "project_id": project_id,
                            "item": item,
                            "base_url": adapter.base_url,
                            "headers": adapter.auth_headers() if hasattr(adapter, "auth_headers") else {},
                            "timeout": 10,
                        })
                        cost_results.append(res)

                state["created_project"] = cp
                state["project_id"] = project_id
                state["added_items"] = cost_results
    except Exception as e:
        print(f"Executor error: {e}")
        state["docs"] = [{"error": str(e)}]
    return state


def _render_sources(docs: List[Dict[str, Any]], k: int = 3) -> str:
    out = []
    for i, d in enumerate(docs[:k], 1):
        meta = d.get("metadata", {})
        src = meta.get("source") or meta.get("file") or meta.get("path") or "documentation"
        out.append(f"{i}. {src}")
    if not out:
        return ""
    return "\n\n**Sources**:\n" + "\n".join(out)


def synthesizer_node(state: AgentState) -> AgentState:
    """Draft the final answer with LLM (fallback to templated if quota/rate-limit)."""
    _append_event(state, "synthesizer")

    query = state.get("user_query") or ""
    api_status = state.get("api_status") or {"status": "N/A"}
    docs = state.get("docs") or []
    plan = state.get("plan") or []

    system = (
        "You are ConTech API Integration Co-Pilot. "
        "Be concise, accurate, and include cURL + Python `requests` when helpful. "
        "If API status is present, summarise it first. If plan exists, summarise steps. "
        "Ground answers in retrieved docs when available and call that out as 'Sources'."
    )
    fewshot = "Return no more than ~300 words."

    try:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                ("human",
                 "User query:\n{query}\n\n"
                 "API status (if any):\n{api_status}\n\n"
                 "Plan (if any):\n{plan}\n\n"
                 "Top doc snippets (if any):\n{docs}\n\n"
                 f"{fewshot}")
            ]
        )
        chain = prompt | llm
        rendered_docs = json.dumps(docs, ensure_ascii=False)[:4000]
        rendered_plan = json.dumps(plan, ensure_ascii=False)[:1500]
        # Avoid passing 'skipped' status into the LLM prompt
        api_status_for_prompt = api_status
        try:
            if isinstance(api_status, dict) and api_status.get("status") == "skipped":
                api_status_for_prompt = {"status": "N/A"}
        except Exception:
            api_status_for_prompt = api_status
        msg = chain.invoke(
            {
                "query": query,
                "api_status": api_status_for_prompt,
                "plan": rendered_plan,
                "docs": rendered_docs,
            }
        )
        answer = msg.content if hasattr(msg, "content") else str(msg)
    except Exception as e:
        # Fallback plain synth if model is unavailable
        answer = (
            f"Placeholder synthesized response for query: '{query}'. "
            f"(LLM error: {e})"
        )

    # Append execution results if present
    try:
        pid = state.get("project_id")
        if pid:
            added = state.get("added_items") or []
            exec_lines = ["Execution Results:", f"- Created projectId: {pid}"]
            try:
                summaries = []
                for r in added:
                    if isinstance(r, dict) and r.get("ok") and isinstance(r.get("data"), dict):
                        summaries.append(json.dumps(r["data"], ensure_ascii=False))
                if summaries:
                    exec_lines.append("- Add cost items responses: " + "; ".join(summaries))
            except Exception:
                pass
            exec_block = "\n".join(exec_lines)
            answer = exec_block + "\n\n" + (answer or "")
    except Exception:
        pass

    # Add a short source list for the Streamlit/UI side
    answer += _render_sources(docs)
    state["answer"] = answer
    return state


def prioritization_node(state: AgentState) -> AgentState:
    """Very lightweight PM scoring so the UI always gets a structured block."""
    _append_event(state, "prioritization")
    q = (state.get("user_query") or "").lower()

    freq = 2  # 1–5
    gap = 2
    risk = 2
    if any(k in q for k in ["auth", "authenticate", "api key", "token"]):
        freq, gap, risk = 4, 4, 3
    if "503" in q or "error" in q or "down" in q:
        freq, gap, risk = 3, 3, 4
    if "create a project" in q and "cost" in q:
        freq, gap, risk = 3, 4, 3

    state["pm_score"] = {
        "pain_frequency": freq,
        "doc_gap": gap,
        "systemic_risk": risk,
        "recommendation": (
            "Add end-to-end examples and quickstarts; ensure auth + common workflows "
            "are clearly documented with request/response samples."
        ),
    }
    return state

# --- Graph wiring --------------------------------------------------------------
def route_edge_selector(state: AgentState) -> str:
    """Return the name of the next node based on state['route']."""
    route = state.get("route") or "synthesizer"
    # Map symbolic route ? node id
    if route == "planner":
        return "planner"
    if route == "executor":
        return "executor"
    return "synthesizer"

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("health", health_check_node)
    graph.add_node("router", router_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("prioritization", prioritization_node)

    # Start → health → router → (conditional) → synth/executor/planner → synthesizer → prioritization → END
    graph.set_entry_point("health")
    graph.add_edge("health", "router")
    graph.add_conditional_edges("router", route_edge_selector, {
        "planner": "planner",
        "executor": "executor",
        "synthesizer": "synthesizer",
    })
    # If planner ran, go executor (RAG) next, then synth
    graph.add_edge("planner", "executor")
    # From executor, go synth
    graph.add_edge("executor", "synthesizer")
    # From synth, go PM
    graph.add_edge("synthesizer", "prioritization")
    # Finish
    graph.add_edge("prioritization", END)

    return graph.compile()

# --- Demo runner ---------------------------------------------------------------
def run_once(app, query: str):
    init: AgentState = {"user_query": query}
    print("\n\n===== Running Query:", query, "=====")
    final = app.invoke(init)

    # Pretty print essential data
    print("\n--- Final State ---")
    print("API Status:", final.get("api_status"))
    print("Retrieved Docs:", bool(final.get("docs")))
    print("Plan Generated:", bool(final.get("plan")))
    # Execution summary (if any)
    pid = final.get("project_id")
    if pid:
        added = final.get("added_items") or []
        try:
            print("Execution: project_id:", pid)
            print("Execution: cost items added:", len(added))
        except Exception:
            pass
    ans = final.get("answer") or ""
    snippet = ans if len(ans) < 800 else ans[:800]
    print("\n--- Final Response (truncated) ---")
    print(snippet)
    return final

# --- Public single-turn entrypoint for web/REST ---
def run_agent_once(user_query: str) -> dict:
    """
    Runs one agent turn for a given user query and returns a dict:
    {
      "selected_api": "<name>",
      "api_base_url": "<url>",
      "api_status": {...} | None,
      "retrieved_docs": [...],
      "plan_generated": bool,
      "final_text": "<concise answer to user>"
    }
    """
    try:
        app = build_graph()
        init_state: AgentState = {"user_query": user_query}
        final = app.invoke(init_state)

        sel = final.get("selected_api") or {}
        api_name = sel.get("name") if isinstance(sel, dict) else None
        api_url = sel.get("base_url") if isinstance(sel, dict) else None

        api_status = final.get("api_status")
        if isinstance(api_status, dict) and api_status.get("status") == "skipped":
            api_status_out = None
        else:
            api_status_out = api_status if isinstance(api_status, dict) else None

        docs = final.get("docs") or []
        plan_generated = bool(final.get("plan"))
        text = final.get("answer") or ""
        # Keep concise: limit to ~5 lines / 800 chars
        lines = [l for l in text.splitlines() if l.strip()]
        short = "\n".join(lines[:6])
        if len(short) > 800:
            short = short[:800]

        return {
            "selected_api": api_name,
            "api_base_url": api_url,
            "api_status": api_status_out,
            "retrieved_docs": docs if isinstance(docs, list) else [],
            "plan_generated": plan_generated,
            "final_text": short,
        }
    except Exception as e:
        return {
            "error": str(e),
            "selected_api": None,
            "api_base_url": None,
            "api_status": None,
            "retrieved_docs": [],
            "plan_generated": False,
            "final_text": "Sorry, something went wrong running the agent.",
        }

def run_demos():
    app = build_graph()
    print("LangGraph compiled.")

    queries = [
        "What is the API status?",
        "How do I authenticate to the API?",
        "Create a project and add some cost items.",
        "Show schedule timeline for project PROJ-ABC123",
        "Hello there!",
        "My API calls are failing with 503 errors.",
    ]
    for q in queries:
        try:
            run_once(app, q)
        except Exception as e:
            print(f"\n[ERROR] while running '{q}': {e}\n")


def run_repl():
    app = build_graph()
    print("LangGraph compiled.")
    try:
        from src.cli.repl import run_repl as _run_repl
        _run_repl(app, agent_module=__import__(__name__))
    except Exception as e:
        print(f"REPL failed: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--repl":
        run_repl()
    else:
        run_demos()



