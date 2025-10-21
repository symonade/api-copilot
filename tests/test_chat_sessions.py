from fastapi.testclient import TestClient
from src.web_app import app


def test_session_grows_and_reset(monkeypatch):
    client = TestClient(app)

    # GET / sets cookie
    r = client.get("/")
    assert r.status_code == 200
    assert "chat_sid" in r.cookies

    # Stub run_agent_once for speed
    def fake_run_once(msg: str):
        return {
            "selected_api": "contech",
            "api_base_url": "http://localhost:8000",
            "api_status": {"status": "Operational"},
            "retrieved_docs": [],
            "plan_generated": False,
            "final_text": "OK",
        }

    import src.web_app as web_app
    monkeypatch.setattr(web_app, "run_agent_once", fake_run_once)

    r = client.post("/chat", data={"message": "Hello"})
    assert r.status_code == 200
    r = client.post("/chat", data={"message": "World"})
    assert r.status_code == 200

    # Fetch transcript and ensure both user lines present
    r = client.get("/chat/transcript")
    assert r.status_code == 200
    txt = r.text
    assert "user: Hello" in txt
    assert "user: World" in txt

    # Reset
    r = client.post("/chat/new")
    assert r.status_code == 200
    r = client.get("/chat/transcript")
    assert r.status_code == 200
    assert r.text.strip() == "" or "No messages" in r.text

