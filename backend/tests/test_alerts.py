from fastapi.testclient import TestClient
from app.main import app
from app.core.security import hash_password, create_access_token
from app.repositories.user_repository import UserRepository
from app.repositories.alert_repository import AlertRepository
from app.services.market.alert_service import AlertService
from app.services.market.advisor_service import AdvisorService

client = TestClient(app)

def test_alert_crud_and_poller():
    # Setup user
    pwd_hash = hash_password("mypassword")
    user = UserRepository.create_user("alerts@gmail.com", pwd_hash, "Alert User", 30)
    token = create_access_token(user["id"])
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create price alert above
    response = client.post("/api/v1/alerts/", json={
        "symbol": "RELIANCE",
        "target_price": 1500.0,
        "condition": "above"
    }, headers=headers)
    assert response.status_code == 200
    alert_id = response.json()["alert_id"]
    assert alert_id is not None

    # 2. Get active alerts - verify created alert is returned
    response = client.get("/api/v1/alerts/", headers=headers)
    assert response.status_code == 200
    alerts = response.json()
    assert len(alerts) == 1
    assert alerts[0]["symbol"] == "RELIANCE"
    assert alerts[0]["target_price"] == 1500.0
    assert alerts[0]["condition"] == "above"
    assert alerts[0]["is_active"] == 1

    # 3. Test background checker with price below target (should NOT trigger)
    original_fetch = AdvisorService._fetch_signals
    AdvisorService._fetch_signals = lambda sym: {"current_price": 1400.0, "rsi": 50.0, "trend": "BULLISH"}
    
    triggered_count = AlertService.check_alerts()
    assert triggered_count == 0
    
    # Verify alert is still active
    active_alerts = AlertRepository.get_active_alerts()
    assert len(active_alerts) == 1
    assert active_alerts[0]["is_active"] == 1

    # 4. Test background checker with price above target (should trigger!)
    AdvisorService._fetch_signals = lambda sym: {"current_price": 1550.0, "rsi": 55.0, "trend": "BULLISH"}
    
    triggered_count = AlertService.check_alerts()
    assert triggered_count == 1
    
    # Verify alert is now inactive (triggered)
    active_alerts = AlertRepository.get_active_alerts()
    assert len(active_alerts) == 0

    # Clean up AdvisorService mock
    AdvisorService._fetch_signals = original_fetch

    # 5. Delete alert
    response = client.delete(f"/api/v1/alerts/{alert_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True
