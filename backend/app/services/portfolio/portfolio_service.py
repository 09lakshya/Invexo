from app.repositories.portfolio_repository import PortfolioRepository
from app.services.market.advisor_service import AdvisorService, UNIVERSE
from app.services.market.ticker_utils import _working_ticker
from app.services.portfolio.statement_parser import parse_statement
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import numpy as np

class PortfolioService:
    @staticmethod
    def _parallel_map(fn, items, workers: int = 8) -> dict:
        """Run `fn` over unique items concurrently, returning {item: result}.

        Live price / ticker lookups hit the network (yfinance) but are
        redis-TTL-cached underneath, so fanning them out only affects the cold
        path — it turns N sequential round-trips into roughly one. Failures map
        to None so a single bad symbol never breaks the whole page.
        """
        items = list(items)
        if not items:
            return {}
        results = {}
        with ThreadPoolExecutor(max_workers=min(workers, len(items))) as executor:
            futures = {executor.submit(fn, item): item for item in items}
            for future in as_completed(futures):
                item = futures[future]
                try:
                    results[item] = future.result()
                except Exception:
                    results[item] = None
        return results

    @staticmethod
    def get_portfolio(user_id: str) -> list[dict]:
        from app.services.market.data_service import DataService
        holdings = PortfolioRepository.get_portfolio(user_id)
        symbols = {h["symbol"] for h in holdings if h.get("symbol")}

        # Fetch every holding's live market price in parallel using DataService
        price_map = PortfolioService._parallel_map(DataService.get_stock_price, symbols)
        # Fetch signals best-effort for technical indicators
        sig_map = PortfolioService._parallel_map(AdvisorService._fetch_signals, symbols)

        enriched = []
        for h in holdings:
            qty = h.get("quantity") or 0
            buy_price = h.get("buy_price") or 0
            invested = qty * buy_price

            signals = sig_map.get(h.get("symbol"))
            live_price = price_map.get(h.get("symbol")) or 0.0

            if live_price > 0:
                curr_price = live_price
            elif signals and signals.get("current_price", 0) > 0:
                curr_price = signals["current_price"]
            else:
                curr_price = buy_price

            has_price = curr_price > 0
            current_value = qty * curr_price if has_price else invested
            pnl = (current_value - invested) if has_price else 0.0
            pnl_percent = (pnl / invested * 100) if (has_price and invested > 0) else 0.0

            enriched.append({
                **h,
                "invested": round(invested, 2),
                "current_price": round(curr_price, 2),
                "current_value": round(current_value, 2),
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_percent, 2),
            })
        return enriched

    @staticmethod
    def add_holding(user_id: str, symbol: str, company_name: str, quantity: float, buy_price: float) -> int | None:
        return PortfolioRepository.add_holding(user_id, symbol, company_name, quantity, buy_price)

    @staticmethod
    def remove_holding(holding_id: int, user_id: str) -> bool:
        return PortfolioRepository.remove_holding(holding_id, user_id)

    @staticmethod
    def preview_import(content: bytes, filename: str, broker: str) -> dict:
        # Parsing errors are surfaced to the caller as ValueError for a 400.
        return parse_statement(content, filename, broker)

    @staticmethod
    def commit_import(user_id: str, holdings: list[dict]) -> int:
        return PortfolioRepository.bulk_add_holdings(user_id, holdings)

    @staticmethod
    def get_portfolio_analytics(user_id: str) -> dict:
        from app.services.market.data_service import DataService
        holdings = PortfolioRepository.get_portfolio(user_id)
        if not holdings:
            return {
                "summary": {
                    "total_investment": 0.0,
                    "total_current_value": 0.0,
                    "total_gain_loss": 0.0,
                    "total_gain_loss_pct": 0.0
                },
                "allocations": {
                    "by_stock": [],
                    "by_sector": {},
                    "by_risk": {}
                },
                "metrics": {
                    "portfolio_beta": 0.0,
                    "portfolio_volatility": 0.0,
                    "sharpe_ratio": 0.0,
                    "value_at_risk_95": 0.0,
                    "diversification_score": 0.0
                },
                "advice": "Add stock holdings to your portfolio to generate real-time analytics and risk suggestions."
            }

        total_investment = 0.0
        total_current_value = 0.0
        
        holding_details = []

        symbols = {h["symbol"] for h in holdings if h.get("symbol")}
        price_map = PortfolioService._parallel_map(DataService.get_stock_price, symbols)
        sig_map = PortfolioService._parallel_map(AdvisorService._fetch_signals, symbols)
        tick_map = PortfolioService._parallel_map(_working_ticker, symbols)

        for holding in holdings:
            symbol = holding["symbol"]
            qty = holding["quantity"]
            buy_price = holding["buy_price"]
            purchase_value = qty * buy_price
            total_investment += purchase_value

            live_price = price_map.get(symbol) or 0.0
            signals = sig_map.get(symbol)
            trend = "BULLISH"
            rsi = 50.0

            if live_price > 0:
                curr_price = live_price
            elif signals and signals.get("current_price", 0) > 0:
                curr_price = signals["current_price"]
            else:
                curr_price = buy_price

            if signals:
                trend = signals.get("trend", "BULLISH")
                rsi = signals.get("rsi", 50.0)

            curr_value = qty * curr_price
            total_current_value += curr_value

            # Get metadata from UNIVERSE
            ticker_symbol = tick_map.get(symbol) or _working_ticker(symbol)
            meta = UNIVERSE.get(ticker_symbol, {})
            sector = meta.get("sector", "Other")
            risk = meta.get("risk", "medium")
            
            holding_details.append({
                "symbol": symbol,
                "quantity": qty,
                "buy_price": buy_price,
                "current_price": curr_price,
                "purchase_value": purchase_value,
                "current_value": curr_value,
                "sector": sector,
                "risk": risk,
                "trend": trend,
                "rsi": rsi
            })

        total_gain_loss = total_current_value - total_investment
        total_gain_loss_pct = (total_gain_loss / total_investment * 100) if total_investment > 0 else 0.0

        # Allocations
        by_stock = []
        by_sector = {}
        by_risk = {}
        
        weighted_beta_sum = 0.0
        weighted_vol_sum = 0.0
        weighted_return_sum = 0.0

        # Approximate values based on risk classifications
        beta_map = {"low": 0.72, "medium": 1.0, "high": 1.42}
        vol_map = {"low": 0.12, "medium": 0.22, "high": 0.38} # Annual volatility

        for detail in holding_details:
            weight = (detail["current_value"] / total_current_value) if total_current_value > 0 else (detail["purchase_value"] / total_investment)
            
            # Allocations lists
            by_stock.append({
                "symbol": detail["symbol"],
                "value": detail["current_value"],
                "weight_pct": round(weight * 100, 2)
            })
            
            sector = detail["sector"]
            by_sector[sector] = by_sector.get(sector, 0.0) + (weight * 100)
            
            risk = detail["risk"]
            by_risk[risk] = by_risk.get(risk, 0.0) + (weight * 100)

            # Weighted metrics
            weighted_beta_sum += weight * beta_map.get(risk, 1.0)
            weighted_vol_sum += weight * vol_map.get(risk, 0.22)
            
            # Estimate returns (bullish = 15%, bearish = 3%)
            est_return = 0.15 if detail["trend"] == "BULLISH" else 0.03
            weighted_return_sum += weight * est_return

        # Round allocations
        by_sector = {k: round(v, 2) for k, v in by_sector.items()}
        by_risk = {k: round(v, 2) for k, v in by_risk.items()}

        # Portfolio Volatility & Beta
        portfolio_beta = round(weighted_beta_sum, 2)
        portfolio_volatility = round(weighted_vol_sum, 4)
        
        # Sharpe Ratio (assuming risk free rate of 6% in India)
        rf_rate = 0.06
        sharpe = 0.0
        if portfolio_volatility > 0:
            sharpe = (weighted_return_sum - rf_rate) / portfolio_volatility
        sharpe_ratio = round(max(0.0, sharpe), 2)
        
        # 1-day Value at Risk (VaR) at 95% confidence (Z = 1.65)
        # VaR = Portfolio Value * Volatility * 1.65 * sqrt(1/252)
        daily_volatility = portfolio_volatility / math.sqrt(252)
        value_at_risk_95 = round(total_current_value * daily_volatility * 1.65, 2)

        # Diversification Score
        sector_count = len(by_sector)
        stock_count = len(holdings)
        max_stock_weight = max(item["weight_pct"] for item in by_stock) if by_stock else 100.0
        
        div_score = 0.0
        # Sector component (max 40 pts)
        if sector_count >= 3: div_score += 40
        elif sector_count == 2: div_score += 20
        else: div_score += 10
        
        # Stock count component (max 40 pts)
        if stock_count >= 6: div_score += 40
        elif 3 <= stock_count <= 5: div_score += 25
        else: div_score += 10
        
        # Concentration component (max 20 pts)
        if max_stock_weight <= 25: div_score += 20
        elif max_stock_weight <= 50: div_score += 10
        else: div_score += 5
        
        # Advice generation
        advice = ""
        if div_score < 40:
            advice = "Your portfolio is highly concentrated. Consider diversifying across at least 3 sectors and adding 3-4 more stocks to reduce unsystematic risk."
        elif portfolio_beta > 1.25:
            advice = "Your portfolio has a high Beta, making it more volatile than the index. Consider accumulating defensive sectors (IT, FMCG) to balance your volatility."
        elif max_stock_weight > 40:
            advice = f"A single stock holds {max_stock_weight}% of your portfolio. Consider rebalancing some capital to keep individual allocations under 25%."
        else:
            advice = "Your portfolio is well-balanced and diversified. Continue checking technical indicators periodically for rebalancing opportunities."

        return {
            "summary": {
                "total_investment": round(total_investment, 2),
                "total_current_value": round(total_current_value, 2),
                "total_gain_loss": round(total_gain_loss, 2),
                "total_gain_loss_pct": round(total_gain_loss_pct, 2)
            },
            "allocations": {
                "by_stock": by_stock,
                "by_sector": by_sector,
                "by_risk": by_risk
            },
            "metrics": {
                "portfolio_beta": portfolio_beta,
                "portfolio_volatility_annual": round(portfolio_volatility * 100, 2),
                "sharpe_ratio": sharpe_ratio,
                "value_at_risk_95": value_at_risk_95,
                "diversification_score": div_score
            },
            "advice": advice
        }
