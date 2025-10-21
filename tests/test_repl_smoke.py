import glob
import os
import time

from src.agent import build_graph
from src.cli.repl import process_line, _process_slash, SessionConfig
from src.apis import ApiRegistry, ContechApi, SchedulerApi


def test_repl_export_smoke(tmp_path):
    # Ensure runs/ writes go under tmp (monkeypatch CWD)
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        app = build_graph()
        session = []
        # Send a simple query
        out = process_line(app, "What is the API status?", session_state=session)
        assert isinstance(out, str)
        assert any(t.get("role") == "assistant" for t in session)

        # Export via command
        cfg = SessionConfig(model="test", max_tokens=128)
        reg = ApiRegistry(); reg.register(ContechApi()); reg.register(SchedulerApi())
        msg = _process_slash("/export", session_state=session, config=cfg, registry=reg, agent_module=None)
        assert "Exported:" in msg
        # Files exist
        md = glob.glob("runs/*.md"); js = glob.glob("runs/*.json")
        assert md and js
    finally:
        os.chdir(cwd)

