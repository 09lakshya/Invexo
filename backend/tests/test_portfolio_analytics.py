from fastapi.testclient import TestClient
from app.main import app
from app.core.security import hash_password, create_access_token
from app.repositories.user_repository import UserRepository
from app.services.market.advisor_service import AdvisorService

client = TestClient(app)

def test_portfolio_analytics():
    # Setup user
    pwd_hash = hash_password("mypassword")
    user = UserRepository.create_user("analytics_user@gmail.com", pwd_hash, "Analytics User", 32)
    token = create_access_token(user["id"])
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get analytics on empty portfolio
    response = client.get("/api/v1/portfolio/analytics", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_investment"] == 0.0
    assert "allocations" in data
    assert "metrics" in data
    assert "advice" in data

    # Mock signals for yfinance to return fixed values for analytics calculations
    original_fetch = AdvisorService._fetch_signals
    AdvisorService._fetch_signals = lambda sym: {"current_price": 2000.0, "rsi": 50.0, "trend": "BULLISH"}

    # 2. Add two stock holdings
    # Add RELIANCE: 10 shares @ ₹1800 (Value = 18000)
    response = client.post("/api/v1/portfolio/add", json={
        "symbol": "RELIANCE",
        "company_name": "Reliance Industries",
        "quantity": 10.0,
        "buy_price": 1800.0
    }, headers=headers)
    assert response.status_code == 200

    # Add TCS: 5 shares @ ₹3000 (Value = 15000)
    response = client.post("/api/v1/portfolio/add", json={
        "symbol": "TCS",
        "company_name": "Tata Consultancy Services",
        "quantity": 5.0,
        "buy_price": 3000.0
    }, headers=headers)
    assert response.status_code == 200

    # 3. Get portfolio analytics
    # Total investment = 10 * 1800 + 5 * 3000 = 18000 + 15000 = 33000
    # Current value = 10 * 2000 + 5 * 2000 = 20000 + 10000 = 30000
    response = client.get("/api/v1/portfolio/analytics", headers=headers)
    assert response.status_code == 200
    analytics = response.json()
    
    assert analytics["summary"]["total_investment"] == 33000.0
    assert analytics["summary"]["total_current_value"] == 30000.0
    assert analytics["summary"]["total_gain_loss"] == -3000.0
    
    # Assert allocations exist
    assert len(analytics["allocations"]["by_stock"]) == 2
    assert "by_sector" in analytics["allocations"]
    assert "by_risk" in analytics["allocations"]
    
    # Assert metrics exist and are calculated
    assert analytics["metrics"]["portfolio_beta"] > 0.0
    assert "value_at_risk_95" in analytics["metrics"]
    assert analytics["metrics"]["diversification_score"] > 0
    assert len(analytics["advice"]) > 0

    # Clean up AdvisorService mock
    AdvisorService._fetch_signals = original_fetch
