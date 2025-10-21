import os
from fastapi.testclient import TestClient

from src.web_app import app, run_agent_once as real_run_once


def test_health_and_index():
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    r = client.get("/")
    assert r.status_code == 200
    assert "chat-window" in r.text


def test_chat_with_and_without_key(monkeypatch):
    client = TestClient(app)

    # Stub run_agent_once to avoid heavy graph/LLM in test
    def fake_run_once(msg: str):
        return {
            "selected_api": "contech",
            "api_base_url": "http://localhost:8000",
            "api_status": {"status": "Operational"},
            "retrieved_docs": [],
            "plan_generated": False,
            "final_text": "Auth via X-API-Key header.",
        }

    monkeypatch.setattr("src.web_app.run_agent_once", fake_run_once, raising=False)

    # Without key (no env) → allowed
    r = client.post("/chat", data={"message": "How do I authenticate?"})
    assert r.status_code == 200
    assert "Auth via X-API-Key" in r.text

    # With key set → require header
    monkeypatch.setenv("PUBLIC_CHAT_API_KEY", "abc123")
    r = client.post("/chat", data={"message": "How do I authenticate?"})
    assert r.status_code == 401
    r = client.post("/chat", data={"message": "How do I authenticate?"}, headers={"X-Public-Key": "abc123"})
    assert r.status_code == 200
