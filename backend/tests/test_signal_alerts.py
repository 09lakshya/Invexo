"""
Tests for buy/sell signal alerts: subscription CRUD, the scan/flip-detection
poller (BUY→hold→SELL, confidence gating, NEUTRAL, auto watchlist coverage),
email delivery, and the in-app notification feed.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import hash_password, create_access_token
from app.core.database import get_db_connection
from app.repositories.user_repository import UserRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.repositories.signal_alert_repository import SignalAlertRepository
from app.services.market.signal_alert_service import SignalAlertService
from app.services.ai.prediction_service import PredictionService
from app.services.auth.auth_service import AuthService

client = TestClient(app)


@pytest.fixture(autouse=True)
def signal_alert_tables():
    """These tables aren't in the shared conftest schema, so create them and
    clear them around every test for isolation."""
    SignalAlertRepository.init_signal_alert_db()
    conn, _ = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM signal_notifications")
    c.execute("DELETE FROM signal_alert_subscriptions")
    conn.commit()
    yield


def _mock_prediction(trend, confidence, price=100.0):
    return lambda symbol: {
        "trend": trend, "confidence": confidence, "current_price": price,
        "rsi": 55.0, "regime": "trending",
    }


def _auth_user(email, name="Signal User"):
    user = UserRepository.create_user(email, hash_password("pw"), name, 30)
    token = create_access_token(user["id"])
    return user, {"Authorization": f"Bearer {token}"}


def test_subscription_crud():
    _, headers = _auth_user("sub@gmail.com")

    resp = client.post("/api/v1/signal-alerts/subscriptions",
                       json={"symbol": "RELIANCE", "min_confidence": 70}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["subscription_id"] is not None

    resp = client.get("/api/v1/signal-alerts/subscriptions", headers=headers)
    assert resp.status_code == 200
    subs = resp.json()
    assert len(subs) == 1
    assert subs[0]["symbol"] == "RELIANCE"
    assert subs[0]["min_confidence"] == 70
    sub_id = subs[0]["id"]

    # Re-subscribing the same symbol is idempotent (updates in place).
    resp = client.post("/api/v1/signal-alerts/subscriptions",
                       json={"symbol": "RELIANCE.NS", "min_confidence": 80}, headers=headers)
    assert resp.status_code == 200
    subs = client.get("/api/v1/signal-alerts/subscriptions", headers=headers).json()
    assert len(subs) == 1
    assert subs[0]["min_confidence"] == 80

    resp = client.delete(f"/api/v1/signal-alerts/subscriptions/{sub_id}", headers=headers)
    assert resp.status_code == 200
    assert client.get("/api/v1/signal-alerts/subscriptions", headers=headers).json() == []


def test_flip_detection_buy_hold_sell():
    user, _ = _auth_user("flip@gmail.com")
    SignalAlertRepository.create_subscription(user["id"], "TCS", 60)

    original = PredictionService.predict_stock
    try:
        # First BULLISH read → one BUY notification.
        PredictionService.predict_stock = staticmethod(_mock_prediction("BULLISH", 80))
        assert SignalAlertService.scan_and_notify()["notified"] == 1

        # Still BULLISH → no flip, no new notification.
        assert SignalAlertService.scan_and_notify()["notified"] == 0

        # NEUTRAL → not actionable, still nothing.
        PredictionService.predict_stock = staticmethod(_mock_prediction("NEUTRAL", 90))
        assert SignalAlertService.scan_and_notify()["notified"] == 0

        # BEARISH → flip to SELL, one new notification.
        PredictionService.predict_stock = staticmethod(_mock_prediction("BEARISH", 75))
        assert SignalAlertService.scan_and_notify()["notified"] == 1
    finally:
        PredictionService.predict_stock = original

    notifs = SignalAlertRepository.get_user_notifications(user["id"], 20, 0)
    actions = [n["action"] for n in notifs]  # newest first
    assert actions == ["SELL", "BUY"]


def test_confidence_gating():
    user, _ = _auth_user("gate@gmail.com")
    SignalAlertRepository.create_subscription(user["id"], "INFY", 70)

    original = PredictionService.predict_stock
    try:
        # Below the user's threshold → suppressed.
        PredictionService.predict_stock = staticmethod(_mock_prediction("BULLISH", 65))
        assert SignalAlertService.scan_and_notify()["notified"] == 0
        # At/above threshold → fires.
        PredictionService.predict_stock = staticmethod(_mock_prediction("BULLISH", 72))
        assert SignalAlertService.scan_and_notify()["notified"] == 1
    finally:
        PredictionService.predict_stock = original


def test_watchlist_auto_coverage_and_email():
    user, _ = _auth_user("auto@gmail.com")
    WatchlistRepository.add_to_watchlist(user["id"], "HDFCBANK")

    sent = []
    original_send = AuthService._send_email
    original_pred = PredictionService.predict_stock
    AuthService._send_email = staticmethod(
        lambda to, subject, text, html=None, reply_to=None: sent.append(
            {"to": to, "subject": subject, "text": text, "html": html}
        ) or True
    )
    # Auto coverage uses the stricter AUTO_MIN_CONFIDENCE (65); 68 clears it.
    PredictionService.predict_stock = staticmethod(_mock_prediction("BULLISH", 68))
    try:
        result = SignalAlertService.scan_and_notify()
    finally:
        AuthService._send_email = original_send
        PredictionService.predict_stock = original_pred

    assert result["notified"] == 1
    matching = [m for m in sent if m["to"] == "auto@gmail.com"]
    assert len(matching) == 1
    assert "BUY" in matching[0]["subject"]
    assert "HDFCBANK" in matching[0]["subject"]
    assert matching[0]["html"] is not None


def test_notifications_feed_and_read():
    user, headers = _auth_user("feed@gmail.com")
    SignalAlertRepository.create_subscription(user["id"], "WIPRO", 60)

    original = PredictionService.predict_stock
    try:
        PredictionService.predict_stock = staticmethod(_mock_prediction("BULLISH", 80))
        SignalAlertService.scan_and_notify()
    finally:
        PredictionService.predict_stock = original

    resp = client.get("/api/v1/signal-alerts/notifications", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] == 1
    assert body["count"] == 1
    notif_id = body["notifications"][0]["id"]
    assert body["notifications"][0]["action"] == "BUY"

    assert client.post(f"/api/v1/signal-alerts/notifications/{notif_id}/read", headers=headers).status_code == 200
    assert client.get("/api/v1/signal-alerts/notifications/unread-count", headers=headers).json()["unread_count"] == 0
