from app.repositories.alert_repository import AlertRepository
from app.repositories.user_repository import UserRepository
from app.services.market.advisor_service import AdvisorService
from app.services.auth.auth_service import AuthService
from app.utils.logger import get_logger

logger = get_logger("alert_service")

APP_URL = "https://invexo.co.in"


class AlertService:
    @staticmethod
    def check_alerts() -> int:
        """
        Scans all active alerts, retrieves live market prices,
        and triggers alerts if conditions are met.
        Returns the count of triggered alerts.
        """
        active_alerts = AlertRepository.get_active_alerts()
        if not active_alerts:
            return 0

        # Group alerts by symbol to minimize yfinance network requests
        symbols = {alert["symbol"] for alert in active_alerts}
        symbol_prices = {}

        for symbol in symbols:
            try:
                # Reuse AdvisorService cached/live signal fetch to retrieve the current price
                signals = AdvisorService._fetch_signals(symbol)
                if signals and "current_price" in signals:
                    symbol_prices[symbol] = signals["current_price"]
            except Exception as e:
                logger.error(f"Failed to fetch current price for alert symbol {symbol}: {e}")

        # Cache user lookups within this run so repeat alerts for one user
        # don't hit the DB more than once.
        user_cache: dict[int, dict | None] = {}

        triggered_count = 0
        for alert in active_alerts:
            symbol = alert["symbol"]
            if symbol not in symbol_prices:
                continue

            current_price = symbol_prices[symbol]
            target_price = alert["target_price"]
            condition = alert["condition"]
            alert_id = alert["id"]

            is_triggered = False
            if condition == "above" and current_price >= target_price:
                is_triggered = True
            elif condition == "below" and current_price <= target_price:
                is_triggered = True

            if is_triggered:
                success = AlertRepository.trigger_alert(alert_id)
                if success:
                    triggered_count += 1
                    logger.info(
                        f"[ALERT TRIGGERED] Alert #{alert_id} for User {alert['user_id']}: "
                        f"{symbol} price {current_price} crossed target {target_price} ({condition})"
                    )

                    # Notify the user on their registered email (best-effort;
                    # a delivery failure must not affect the triggered state).
                    user_id = alert["user_id"]
                    if user_id not in user_cache:
                        try:
                            user_cache[user_id] = UserRepository.get_user_by_id(user_id)
                        except Exception as e:
                            logger.error(f"Failed to load user {user_id} for alert email: {e}")
                            user_cache[user_id] = None

                    user = user_cache[user_id]
                    if user and user.get("email"):
                        AlertService._send_target_reached_email(user, alert, current_price)
                    else:
                        logger.warning(
                            f"No email on file for user {user_id}; skipping alert notification for #{alert_id}"
                        )

        return triggered_count

    @staticmethod
    def _send_target_reached_email(user: dict, alert: dict, current_price: float) -> None:
        """Sends a 'target reached' notification to the user's registered email."""
        email_addr = user["email"]
        name = user.get("name") or "there"
        symbol = alert["symbol"]
        target_price = alert["target_price"]
        condition = alert["condition"]
        direction = "risen above" if condition == "above" else "fallen below"

        subject = f"🎯 Target reached: {symbol} is now ₹{current_price:,.2f}"

        text_content = (
            f"Hi {name},\n\n"
            f"Good news — your price target for {symbol} has been reached.\n\n"
            f"{symbol} has {direction} your target of ₹{target_price:,.2f} "
            f"and is currently trading at ₹{current_price:,.2f}.\n\n"
            f"Review {symbol} on Invexo: {APP_URL}/stock/{symbol}\n\n"
            f"You're receiving this because you set a price alert on Invexo.\n"
            f"— The Invexo Team"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#0b0f19;color:#f3f4f6;padding:24px;margin:0;">
  <div style="max-width:600px;margin:0 auto;background:linear-gradient(135deg,#111827,#0f172a);border:1px solid #1e293b;border-radius:16px;padding:36px;">
    <div style="font-size:24px;font-weight:800;background:linear-gradient(to right,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">INVEXO</div>
    <h1 style="font-size:22px;color:#ffffff;margin:20px 0 8px;">🎯 Target reached</h1>
    <p style="font-size:15px;line-height:1.6;color:#cbd5e1;margin:0 0 20px;">
      Hi {name}, your price alert for <strong style="color:#ffffff;">{symbol}</strong> has just been triggered.
    </p>
    <div style="margin:20px 0;padding:20px;background:#0f172a;border:1px solid #1e293b;border-radius:12px;">
      <table style="width:100%;border-collapse:collapse;font-size:14px;color:#cbd5e1;">
        <tr>
          <td style="padding:8px 0;color:#94a3b8;">Symbol</td>
          <td style="padding:8px 0;text-align:right;color:#ffffff;font-weight:600;">{symbol}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#94a3b8;">Your target</td>
          <td style="padding:8px 0;text-align:right;color:#e2e8f0;">Price {condition} ₹{target_price:,.2f}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#94a3b8;">Current price</td>
          <td style="padding:8px 0;text-align:right;color:#34d399;font-weight:700;font-size:16px;">₹{current_price:,.2f}</td>
        </tr>
      </table>
    </div>
    <a href="{APP_URL}/stock/{symbol}" style="display:block;width:fit-content;margin:28px auto 8px;padding:14px 28px;background:linear-gradient(135deg,#6366f1,#4f46e5);color:#ffffff;text-decoration:none;font-weight:600;border-radius:8px;box-shadow:0 4px 14px rgba(99,102,241,0.4);">View {symbol} on Invexo</a>
    <p style="font-size:12px;color:#64748b;margin-top:28px;padding-top:20px;border-top:1px solid #1e293b;text-align:center;">
      You're receiving this because you set a price alert on Invexo.<br>
      This email was sent to {email_addr}.
    </p>
  </div>
</body>
</html>"""

        try:
            delivered = AuthService._send_email(email_addr, subject, text_content, html=html_content)
            if delivered:
                logger.info(f"[ALERT EMAIL] Sent target-reached notification for {symbol} to {email_addr}")
            else:
                logger.error(f"[ALERT EMAIL] Failed to send target-reached notification for {symbol} to {email_addr}")
        except Exception as e:
            logger.error(f"[ALERT EMAIL] Error sending target-reached notification to {email_addr}: {e}")
