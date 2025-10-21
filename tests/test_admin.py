from fastapi.testclient import TestClient
from src.web_app import app


def test_admin_auth_and_metrics(monkeypatch):
    client = TestClient(app)
    # No secret → unauthorized
    r = client.get("/admin")
    assert r.status_code in (401, 403)

    # Set secret
    monkeypatch.setenv("ADMIN_SECRET", "adminkey")

    # Hit chat a couple times (stub agent)
    import src.web_app as web_app
    def fake_run_once(msg: str):
        return {"selected_api": "contech", "api_status": {"status": "Operational"}, "final_text": "ok", "retrieved_docs": [], "plan_generated": False}
    web_app.run_agent_once = fake_run_once

    client.get("/")
    client.post("/chat", data={"message": "hi"})
    client.post("/chat/share")

    r = client.get("/admin?key=adminkey")
    assert r.status_code == 200
    r = client.get("/admin/metrics.json?key=adminkey")
    assert r.status_code == 200
    data = r.json()
    assert "daily" in data and "totals" in data
    r = client.get("/admin/export.csv?key=adminkey")
    assert r.status_code == 200
    assert r.text.startswith("day,")

