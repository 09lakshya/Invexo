from fastapi.testclient import TestClient
from app.main import app
from app.core.security import hash_password, create_access_token
from app.repositories.user_repository import UserRepository
from app.repositories.alert_repository import AlertRepository
import app.services.ai.copilot_service as cs

client = TestClient(app)

def test_copilot_chat_intent_parsing():
    # Setup user
    pwd_hash = hash_password("mypassword")
    user = UserRepository.create_user("copilot@gmail.com", pwd_hash, "Copilot User", 25)
    token = create_access_token(user["id"])
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test greeting / default fallback
    response = client.post("/api/v1/copilot/chat", json={"message": "hello there"}, headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert "response" in res_data
    assert "Vexo" in res_data["response"]

    # 2. Test portfolio keyword
    response = client.post("/api/v1/copilot/chat", json={"message": "can you check my portfolio holdings?"}, headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert "empty" in res_data["response"] or "investment" in res_data["response"].lower()

    # 3. Test watchlist keyword
    response = client.post("/api/v1/copilot/chat", json={"message": "show me my watchlist"}, headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert "watchlist" in res_data["response"].lower()

    # 4. Test stock symbol keyword
    response = client.post("/api/v1/copilot/chat", json={"message": "what is the technical setup of RELIANCE?"}, headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert "RELIANCE" in res_data["response"]
    assert "RSI" in res_data["response"]


# ── Tool-calling agent tests (Gemini mocked) ────────────────────────────────

class _FakeResp:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def _model_functioncall(name, args):
    return {"candidates": [{"content": {"role": "model", "parts": [
        {"functionCall": {"name": name, "args": args}}
    ]}}]}


def _model_text(text):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]}


def _agent_user():
    user = UserRepository.create_user("vexo@gmail.com", hash_password("pw"), "Vexo User", 30)
    token = create_access_token(user["id"])
    return {"Authorization": f"Bearer {token}"}, user["id"]


def test_agent_runs_prediction_tool(monkeypatch):
    """User asks for a prediction -> agent calls get_stock_prediction, then answers."""
    headers, _ = _agent_user()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    # Stub the tool dispatcher so no network / yfinance is touched.
    monkeypatch.setattr(
        cs, "execute_tool",
        lambda uid, name, args: {"symbol": "RELIANCE", "ml_predicted_price": 1478.5}
        if name == "get_stock_prediction" else {"error": "unexpected tool"},
    )

    state = {"round": 0, "saw_tool": False}

    def fake_post(url, json=None, headers=None, timeout=None):
        state["round"] += 1
        assert json["tools"][0]["function_declarations"]
        assert "system_instruction" in json
        if state["round"] == 1:
            return _FakeResp(_model_functioncall("get_stock_prediction", {"symbol": "RELIANCE"}))
        assert json["contents"][-1]["parts"][0]["functionResponse"]["name"] == "get_stock_prediction"
        state["saw_tool"] = True
        return _FakeResp(_model_text("RELIANCE is predicted at 1478.5."))

    monkeypatch.setattr(cs.requests, "post", fake_post)

    res = client.post("/api/v1/copilot/chat", json={"message": "predict reliance"}, headers=headers)
    assert res.status_code == 200
    assert "1478.5" in res.json()["response"]
    assert state["round"] == 2 and state["saw_tool"]


def test_agent_create_alert_action_persists(monkeypatch):
    """The agent can take a real action: creating a price alert writes to the DB."""
    headers, user_id = _agent_user()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    state = {"round": 0}

    def fake_post(url, json=None, headers=None, timeout=None):
        state["round"] += 1
        if state["round"] == 1:
            return _FakeResp(_model_functioncall(
                "create_price_alert", {"symbol": "TCS", "target_price": 3500, "condition": "above"}))
        return _FakeResp(_model_text("Done — I'll alert you when TCS crosses 3500."))

    monkeypatch.setattr(cs.requests, "post", fake_post)

    res = client.post("/api/v1/copilot/chat",
                      json={"message": "alert me when TCS goes above 3500"}, headers=headers)
    assert res.status_code == 200
    alerts = AlertRepository.get_user_alerts(user_id)
    assert len(alerts) == 1
    assert alerts[0]["symbol"] == "TCS"
    assert alerts[0]["target_price"] == 3500
    assert alerts[0]["condition"] == "above"


def test_history_is_passed_through(monkeypatch):
    """Prior conversation turns are forwarded to the model for memory."""
    headers, _ = _agent_user()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["contents"] = json["contents"]
        return _FakeResp(_model_text("ok"))

    monkeypatch.setattr(cs.requests, "post", fake_post)

    res = client.post(
        "/api/v1/copilot/chat",
        json={
            "message": "and what about now?",
            "history": [
                {"sender": "user", "text": "how is INFY?"},
                {"sender": "copilot", "text": "INFY looks bullish."},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 200
    contents = captured["contents"]
    assert len(contents) == 3  # 2 history turns + current message
    assert contents[0]["role"] == "user" and "INFY" in contents[0]["parts"][0]["text"]
    assert contents[1]["role"] == "model"
    assert contents[-1]["parts"][0]["text"] == "and what about now?"
