from fastapi.testclient import TestClient
from app.main import app
from app.core.security import hash_password, create_access_token
from app.repositories.user_repository import UserRepository

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
    assert "Invexo Copilot" in res_data["response"]

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
