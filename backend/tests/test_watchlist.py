from fastapi.testclient import TestClient
from app.main import app
from app.core.security import hash_password, create_access_token
from app.repositories.user_repository import UserRepository

client = TestClient(app)

def test_watchlist_operations():
    # Setup user
    pwd_hash = hash_password("mypassword")
    user = UserRepository.create_user("watchlist@gmail.com", pwd_hash, "Watchlist User", 28)
    token = create_access_token(user["id"])
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Add symbol to watchlist
    response = client.post("/api/v1/watchlist/", json={"symbol": "RELIANCE"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 2. Duplicate symbol should fail (return 400)
    response = client.post("/api/v1/watchlist/", json={"symbol": "RELIANCE"}, headers=headers)
    assert response.status_code == 400

    # 3. Get watchlist - should include RELIANCE with signals
    response = client.get("/api/v1/watchlist/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "RELIANCE"
    assert "current_price" in data[0]
    assert "trend" in data[0]

    # 4. Remove symbol
    response = client.delete("/api/v1/watchlist/RELIANCE", headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 5. Get watchlist - should be empty now
    response = client.get("/api/v1/watchlist/", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 0

    # 6. Delete non-existent symbol should return 404
    response = client.delete("/api/v1/watchlist/RELIANCE", headers=headers)
    assert response.status_code == 404
