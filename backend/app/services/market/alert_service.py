from app.repositories.alert_repository import AlertRepository
from app.services.market.advisor_service import AdvisorService
from app.utils.logger import get_logger

logger = get_logger("alert_service")

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

        return triggered_count
