"""
Buy/Sell signal alerts.

Scans the consensus predictor over every symbol any user cares about — their
explicit signal-alert subscriptions plus the automatic coverage of their
watchlist and holdings — and notifies them (in-app feed + email) when the
predicted trend *flips* into an actionable BUY (BULLISH) or SELL (BEARISH)
call at or above their confidence threshold.

Design notes:
  * We only notify on a flip. If the last thing we told a user about a symbol
    was BUY and it's still BULLISH, we stay silent; a BEARISH read then emits a
    single SELL. NEUTRAL is never notified and never resets the last action, so
    a genuine BUY→SELL flip is still caught after a neutral patch.
  * predict_stock is heavy, so each unique symbol is scored exactly once per
    run regardless of how many users watch it.
  * These are model signals, not investment advice — the copy says so.
"""

from app.repositories.signal_alert_repository import SignalAlertRepository, normalize_symbol
from app.repositories.watchlist_repository import WatchlistRepository
from app.repositories.portfolio_repository import PortfolioRepository
from app.repositories.user_repository import UserRepository
from app.services.ai.prediction_service import PredictionService
from app.services.auth.auth_service import AuthService
from app.utils.logger import get_logger

logger = get_logger("signal_alert_service")

APP_URL = "https://invexo.co.in"

# Automatic (watchlist / holdings) coverage is held to a stricter bar than an
# explicit subscription, since the user didn't ask for signals on it directly.
AUTO_MIN_CONFIDENCE = 65
# Source precedence when a symbol reaches a user through more than one channel.
SOURCE_PRIORITY = {"subscription": 0, "watchlist": 1, "portfolio": 2}


def trend_to_action(trend: str) -> str | None:
    """Consensus trend → actionable call. NEUTRAL is not actionable."""
    t = (trend or "").upper()
    if t == "BULLISH":
        return "BUY"
    if t == "BEARISH":
        return "SELL"
    return None


class SignalAlertService:
    @staticmethod
    def _build_watch_map() -> dict[tuple[int, str], dict]:
        """(user_id, symbol) → {min_confidence, source} for every symbol any
        user should be scanned for. When a symbol reaches a user via multiple
        channels, keep the most permissive threshold and the highest-priority
        source label (subscription > watchlist > portfolio)."""
        watch: dict[tuple[int, str], dict] = {}

        def _merge(user_id: int, symbol: str, min_conf: int, source: str):
            sym = normalize_symbol(symbol)
            if not sym:
                return
            key = (user_id, sym)
            existing = watch.get(key)
            if existing is None:
                watch[key] = {"min_confidence": min_conf, "source": source}
                return
            existing["min_confidence"] = min(existing["min_confidence"], min_conf)
            if SOURCE_PRIORITY.get(source, 9) < SOURCE_PRIORITY.get(existing["source"], 9):
                existing["source"] = source

        for sub in SignalAlertRepository.get_active_subscriptions():
            try:
                _merge(int(sub["user_id"]), sub["symbol"],
                       int(sub.get("min_confidence") or 60), "subscription")
            except (TypeError, ValueError):
                continue

        for entry in WatchlistRepository.get_all_entries():
            try:
                _merge(int(entry["user_id"]), entry["symbol"], AUTO_MIN_CONFIDENCE, "watchlist")
            except (TypeError, ValueError):
                continue

        for holding in PortfolioRepository.get_all_holdings():
            # portfolio user_id is stored as text; convert to the integer id.
            try:
                _merge(int(holding["user_id"]), holding["symbol"], AUTO_MIN_CONFIDENCE, "portfolio")
            except (TypeError, ValueError):
                continue

        return watch

    @staticmethod
    def scan_and_notify() -> dict:
        """Scan every watched symbol once, and emit a notification to each user
        whose signal for that symbol has flipped. Returns run counts."""
        watch = SignalAlertService._build_watch_map()
        if not watch:
            return {"scanned": 0, "notified": 0}

        symbols = sorted({sym for (_uid, sym) in watch})
        predictions: dict[str, dict] = {}
        for sym in symbols:
            try:
                pred = PredictionService.predict_stock(sym)
                if pred and "error" not in pred:
                    predictions[sym] = pred
            except Exception as e:
                logger.error(f"Signal alert prediction failed for {sym}: {e}")

        user_cache: dict[int, dict | None] = {}
        notified = 0

        for (user_id, sym), cfg in watch.items():
            pred = predictions.get(sym)
            if not pred:
                continue

            action = trend_to_action(pred.get("trend"))
            if action is None:
                continue  # NEUTRAL — nothing actionable

            confidence = int(pred.get("confidence") or 0)
            if confidence < cfg["min_confidence"]:
                continue

            # Flip detection: skip if we already told this user the same thing.
            last_action = SignalAlertRepository.get_last_action(user_id, sym)
            if last_action == action:
                continue

            price = pred.get("current_price")
            message = SignalAlertService._build_message(sym, action, confidence, pred)

            notif_id = SignalAlertRepository.insert_notification(
                user_id=user_id, symbol=sym, action=action,
                trend=pred.get("trend"), confidence=confidence, price=price,
                message=message, source=cfg["source"],
            )
            if notif_id is None:
                continue
            notified += 1

            # Email delivery is best-effort — a failure must not undo the
            # in-app notification we already recorded.
            if user_id not in user_cache:
                try:
                    user_cache[user_id] = UserRepository.get_user_by_id(user_id)
                except Exception as e:
                    logger.error(f"Failed to load user {user_id} for signal email: {e}")
                    user_cache[user_id] = None
            user = user_cache[user_id]
            if user and user.get("email"):
                SignalAlertService._send_signal_email(user, sym, action, confidence, price, message)

        logger.info(f"Signal alert scan: {len(symbols)} symbols, {notified} notifications emitted.")
        return {"scanned": len(symbols), "notified": notified}

    @staticmethod
    def _build_message(symbol: str, action: str, confidence: int, pred: dict) -> str:
        trend = (pred.get("trend") or "").title()
        rsi = pred.get("rsi")
        regime = pred.get("regime")
        verb = "turned bullish" if action == "BUY" else "turned bearish"
        bits = [f"{symbol} {verb} — consensus signal is {action} at {confidence}% confidence."]
        if rsi is not None:
            bits.append(f"RSI {rsi}.")
        if regime:
            bits.append(f"Market regime: {regime.replace('_', ' ')}.")
        return " ".join(bits)

    @staticmethod
    def _send_signal_email(user: dict, symbol: str, action: str, confidence: int,
                           price, message: str) -> None:
        email_addr = user["email"]
        name = user.get("name") or "there"
        is_buy = action == "BUY"
        accent = "#34d399" if is_buy else "#f87171"
        emoji = "🟢" if is_buy else "🔴"
        price_str = f"₹{price:,.2f}" if isinstance(price, (int, float)) else "—"

        subject = f"{emoji} {action} signal: {symbol}"

        text_content = (
            f"Hi {name},\n\n"
            f"Invexo's consensus model just issued a {action} signal for {symbol}.\n\n"
            f"{message}\n"
            f"Current price: {price_str}\n\n"
            f"Review {symbol}: {APP_URL}/stock/{symbol}\n\n"
            f"This is an automated model signal, not investment advice. Signals can be "
            f"wrong — do your own research and manage your risk.\n"
            f"You're receiving this because you subscribed to signal alerts or {symbol} "
            f"is in your watchlist or portfolio on Invexo.\n"
            f"— The Invexo Team"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#0b0f19;color:#f3f4f6;padding:24px;margin:0;">
  <div style="max-width:600px;margin:0 auto;background:linear-gradient(135deg,#111827,#0f172a);border:1px solid #1e293b;border-radius:16px;padding:36px;">
    <div style="font-size:24px;font-weight:800;background:linear-gradient(to right,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">INVEXO</div>
    <div style="display:inline-block;margin-top:18px;padding:6px 14px;border-radius:999px;background:{accent}22;color:{accent};font-weight:700;font-size:13px;letter-spacing:0.04em;">{emoji} {action} SIGNAL</div>
    <h1 style="font-size:22px;color:#ffffff;margin:16px 0 8px;">{symbol}</h1>
    <p style="font-size:15px;line-height:1.6;color:#cbd5e1;margin:0 0 20px;">
      Hi {name}, {message}
    </p>
    <div style="margin:20px 0;padding:20px;background:#0f172a;border:1px solid #1e293b;border-radius:12px;">
      <table style="width:100%;border-collapse:collapse;font-size:14px;color:#cbd5e1;">
        <tr>
          <td style="padding:8px 0;color:#94a3b8;">Signal</td>
          <td style="padding:8px 0;text-align:right;color:{accent};font-weight:700;">{action}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#94a3b8;">Confidence</td>
          <td style="padding:8px 0;text-align:right;color:#ffffff;font-weight:600;">{confidence}%</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#94a3b8;">Current price</td>
          <td style="padding:8px 0;text-align:right;color:#e2e8f0;font-weight:600;">{price_str}</td>
        </tr>
      </table>
    </div>
    <a href="{APP_URL}/stock/{symbol}" style="display:block;width:fit-content;margin:28px auto 8px;padding:14px 28px;background:linear-gradient(135deg,#6366f1,#4f46e5);color:#ffffff;text-decoration:none;font-weight:600;border-radius:8px;box-shadow:0 4px 14px rgba(99,102,241,0.4);">View {symbol} on Invexo</a>
    <p style="font-size:12px;color:#64748b;margin-top:28px;padding-top:20px;border-top:1px solid #1e293b;text-align:center;line-height:1.6;">
      This is an automated model signal, not investment advice. Signals can be wrong — do your own research and manage your risk.<br>
      You're receiving this because you subscribed to signal alerts, or {symbol} is in your watchlist or portfolio.<br>
      This email was sent to {email_addr}.
    </p>
  </div>
</body>
</html>"""

        try:
            delivered = AuthService._send_email(email_addr, subject, text_content, html=html_content)
            if delivered:
                logger.info(f"[SIGNAL EMAIL] Sent {action} signal for {symbol} to {email_addr}")
            else:
                logger.error(f"[SIGNAL EMAIL] Failed to send {action} signal for {symbol} to {email_addr}")
        except Exception as e:
            logger.error(f"[SIGNAL EMAIL] Error sending {action} signal to {email_addr}: {e}")
