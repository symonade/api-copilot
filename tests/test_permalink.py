from fastapi.testclient import TestClient
from src.web_app import app


def _stub(client: TestClient):
    def fake_run_once(msg: str):
        return {
            "selected_api": "contech",
            "api_base_url": "http://localhost:8000",
            "api_status": {"status": "Operational"},
            "retrieved_docs": [],
            "plan_generated": False,
            "final_text": f"You asked: {msg}",
        }
    import src.web_app as web_app
    web_app.run_agent_once = fake_run_once


def test_share_and_view_transcript():
    client = TestClient(app)
    _stub(client)

    client.get("/")
    client.post("/chat", data={"message": "Hello"})
    client.post("/chat", data={"message": "World"})

    r = client.post("/chat/share")
    assert r.status_code == 200
    assert "/c/" in r.text
    # Extract token
    import re
    m = re.search(r"/c/([A-Za-z0-9_\-\.]+)", r.text)
    assert m
    token = m.group(1)

    r2 = client.get(f"/c/{token}")
    assert r2.status_code == 200
    assert "Hello" in r2.text and "World" in r2.text

    # Corrupt token
    bad = token[:-1] + ("A" if token[-1] != "A" else "B")
    r3 = client.get(f"/c/{bad}")
    assert r3.status_code in (400, 422)

