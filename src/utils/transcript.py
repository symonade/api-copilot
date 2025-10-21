import json
import os
from datetime import datetime
from typing import Any, Dict, List


def _ensure_runs_dir(path: str) -> None:
    base = os.path.dirname(path)
    if base and not os.path.exists(base):
        os.makedirs(base, exist_ok=True)


def save_transcript_json(session_state: List[Dict[str, Any]], config: Dict[str, Any], path: str) -> None:
    _ensure_runs_dir(path)
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "config": config,
        "turns": session_state,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def save_transcript_md(session_state: List[Dict[str, Any]], config: Dict[str, Any], path: str) -> None:
    _ensure_runs_dir(path)
    lines: List[str] = []
    lines.append(f"# API Copilot Transcript ({datetime.utcnow().isoformat()}Z)")
    lines.append("")
    if config:
        lines.append("## Config")
        for k, v in config.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    lines.append("## Turns")
    for turn in session_state:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        lines.append(f"### {role.title()}")
        lines.append("")
        lines.append(content)
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

