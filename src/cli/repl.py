import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from prompt_toolkit import prompt  # type: ignore
except Exception:  # pragma: no cover
    prompt = input  # fallback

from rich.console import Console
from pathlib import Path

from src.apis import ApiRegistry, ContechApi, SchedulerApi
from src.tools import check_api_status, search_documentation
from src.utils.transcript import save_transcript_json, save_transcript_md

console = Console()


@dataclass
class SessionConfig:
    model: str
    max_tokens: int
    pinned_api: Optional[str] = None  # "contech" | "scheduler" | None


def _read_features() -> Dict[str, Any]:
    rp = Path(__file__).resolve().parents[2] / "product" / "roadmap.json"
    try:
        return json.loads(rp.read_text(encoding="utf-8"))
    except Exception:
        return {"next": [], "later": []}


def _print_features_list() -> None:
    data = _read_features()
    console.rule("Features Coming Soon")
    console.print(f"[dim]Version {data.get('version','')} • Updated {data.get('updated','')}[/dim]")
    nxt = data.get("next", [])
    if nxt:
        console.print("[bold]Next up[/bold]")
        for i in nxt:
            console.print(f" • {i.get('title')}: [dim]{i.get('desc','')}[/dim]")
    later = data.get("later", [])
    if later:
        console.print("[bold]Later[/bold]")
        for i in later:
            console.print(f" • {i.get('title')}: [dim]{i.get('desc','')}[/dim]")


def _timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _select_adapter(query: str, registry: ApiRegistry, config: SessionConfig):
    if config.pinned_api:
        ad = registry.get(config.pinned_api)
        if ad:
            return ad
    return registry.select_for_query(query)


def _process_slash(
    line: str,
    *,
    session_state: List[Dict[str, Any]],
    config: SessionConfig,
    registry: ApiRegistry,
    agent_module,
) -> Optional[str]:
    parts = line.strip().split()
    cmd = parts[0].lower()
    arg = " ".join(parts[1:]) if len(parts) > 1 else ""

    if cmd == "/help":
        return (
            "Commands:\n"
            "/status — health check on current adapter\n"
            "/features — list coming-soon items\n"
            "/reset — clear session history\n"
            "/export — save transcript to runs/ as .md and .json\n"
            "/model <name> — switch model for this session\n"
            "/max_tokens <int> — set output token cap\n"
            "/api <contech|scheduler|auto> — pin routing or return to auto\n"
            "/help — show this help"
        )

    if cmd == "/features":
        _print_features_list()
        return ""

    if cmd == "/reset":
        session_state.clear()
        return "Session cleared."

    if cmd == "/export":
        slug = _timestamp_slug()
        md_path = f"runs/{slug}.md"
        json_path = f"runs/{slug}.json"
        cfg = {"model": config.model, "max_tokens": config.max_tokens, "pinned_api": config.pinned_api}
        save_transcript_md(session_state, cfg, md_path)
        save_transcript_json(session_state, cfg, json_path)
        return f"Exported: {md_path}, {json_path}"

    if cmd == "/status":
        adapter = _select_adapter("status", registry, config)
        res = check_api_status.invoke({"base_url": adapter.base_url})
        return json.dumps(res, ensure_ascii=False)

    if cmd == "/model":
        new_model = arg.strip()
        if not new_model:
            return f"Current model: {config.model}"
        config.model = new_model
        try:
            # re-init LLM on the agent module
            agent_module.llm = agent_module.ChatGoogleGenerativeAI(
                model=config.model,
                max_output_tokens=config.max_tokens,
                temperature=0.2,
            )
            return f"Model set to {config.model}"
        except Exception as e:
            return f"Error setting model: {e}"

    if cmd == "/max_tokens":
        try:
            mt = int(arg.strip())
            config.max_tokens = mt
            # Update agent setting if present
            try:
                agent_module.MAX_OUTPUT_TOKENS = mt
            except Exception:
                pass
            return f"max_tokens set to {mt}"
        except Exception:
            return "Usage: /max_tokens <int>"

    if cmd == "/api":
        val = arg.strip().lower()
        if not val or val == "auto":
            config.pinned_api = None
            return "Routing set to auto."
        if val in ("contech", "scheduler"):
            if registry.get(val):
                config.pinned_api = val
                return f"Pinned API: {val}"
            return f"Adapter '{val}' not found."
        return "Usage: /api <contech|scheduler|auto>"

    return f"Unknown command: {cmd}. Try /help"


def process_line(app, line: str, *, session_state: List[Dict[str, Any]]):
    """Invoke the agent graph once and return assistant text."""
    state: Dict[str, Any] = {"user_query": line}
    final = app.invoke(state)
    ans = final.get("answer") or ""
    session_state.append({"role": "user", "content": line})
    session_state.append({"role": "assistant", "content": ans})
    return ans


def run_repl(app, agent_module):
    console.rule("API Copilot REPL")
    console.print("Type /help for commands. Ctrl+C to exit.\n")

    registry = ApiRegistry()
    registry.register(ContechApi())
    registry.register(SchedulerApi())

    config = SessionConfig(model=getattr(agent_module, "PRIMARY_MODEL", "gemini-2.5-flash-lite"), max_tokens=int(getattr(agent_module, "MAX_OUTPUT_TOKENS", 512)))

    session_state: List[Dict[str, Any]] = []

    while True:
        try:
            line = prompt("copilot> ")
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye.")
            break

        if not line.strip():
            continue

        if line.startswith("/"):
            try:
                out = _process_slash(line, session_state=session_state, config=config, registry=registry, agent_module=agent_module)
            except Exception as e:
                out = f"[command error] {e}"
            if out is not None:
                console.print(out)
            continue

        # Normal agent turn
        try:
            ans = process_line(app, line, session_state=session_state)
            console.print(ans)
        except Exception as e:
            console.print(f"[error] {e}")

