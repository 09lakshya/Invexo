from app.repositories.portfolio_repository import PortfolioRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.market.advisor_service import AdvisorService, UNIVERSE
from app.services.market.ticker_utils import _working_ticker
from app.services.portfolio.portfolio_service import PortfolioService
import os
import requests
import re

class CopilotService:
    @staticmethod
    def get_copilot_response(user_id: int, message: str) -> str:
        # 1. Fetch user portfolio & watchlist context
        holdings = PortfolioRepository.get_portfolio(user_id)
        watchlist = WatchlistRepository.get_watchlist(user_id)
        
        # Gather live indicators for portfolio stocks to build rich context
        portfolio_summary = []
        for h in holdings:
            symbol = h["symbol"]
            signals = AdvisorService._fetch_signals(symbol)
            price = signals.get("current_price", h["buy_price"]) if signals else h["buy_price"]
            portfolio_summary.append({
                "symbol": symbol,
                "company_name": h.get("company_name", ""),
                "qty": h["quantity"],
                "buy_price": h["buy_price"],
                "current_price": price,
                "value": round(h["quantity"] * price, 2)
            })
            
        watchlist_summary = [w["symbol"] for w in watchlist]

        # 2. Check for Gemini API key
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if api_key:
            try:
                # Prepare rich context prompt
                context = (
                    f"You are Invexo Copilot, a highly knowledgeable AI financial analyst. "
                    f"Provide direct, professional, data-backed financial advice to the user. "
                    f"Do not give legal/regulatory disclaimers in every sentence; act as an advanced Copilot assistant.\n\n"
                    f"User's Portfolio:\n{portfolio_summary}\n\n"
                    f"User's Watchlist Tickers:\n{watchlist_summary}\n\n"
                    f"User's Query:\n\"{message}\"\n\n"
                    f"Generate a detailed, helpful financial response in clean markdown."
                )
                
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": context}
                            ]
                        }
                    ]
                }
                
                response = requests.post(api_url, json=payload, headers=headers, timeout=12)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text:
                            return text.strip()
            except Exception:
                # Fall back to offline engine if API call fails
                pass

        # 3. Offline Rule-based Natural Language Processing Fallback Engine
        msg_lower = message.lower()
        
        # Check if user asks about a specific stock (e.g., WIPRO, RELIANCE, TCS)
        detected_symbols = []
        for symbol in UNIVERSE.keys():
            root_symbol = symbol.replace(".NS", "")
            if root_symbol.lower() in msg_lower:
                detected_symbols.append(root_symbol)
                
        if detected_symbols:
            symbol = detected_symbols[0]
            ticker_symbol = _working_ticker(symbol)
            meta = UNIVERSE.get(ticker_symbol, {})
            signals = AdvisorService._fetch_signals(symbol)
            
            if signals:
                price = signals["current_price"]
                rsi = signals["rsi"]
                trend = signals["trend"]
                
                # Check if user owns it
                user_owns = False
                owned_qty = 0.0
                for h in portfolio_summary:
                    if h["symbol"].upper() == symbol.upper():
                        user_owns = True
                        owned_qty = h["qty"]
                        
                owns_text = f"You currently hold **{owned_qty} shares** of {symbol} in your portfolio." if user_owns else f"You do not currently hold {symbol} in your portfolio."
                
                tech_status = "BULLISH" if trend == "BULLISH" else "BEARISH"
                rsi_status = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"
                
                analysis = (
                    f"### 📊 Technical Analysis for **{symbol}** ({meta.get('name', '')})\n"
                    f"*{meta.get('desc', '')}*\n\n"
                    f"* **Current Price**: ₹{price}\n"
                    f"* **Trend**: 📈 {trend} momentum\n"
                    f"* **RSI (14-day)**: {rsi} ({rsi_status} conditions)\n"
                    f"* **Sector**: {meta.get('sector', 'Other')}\n"
                    f"* **Risk Profile**: {meta.get('risk', 'medium')}\n\n"
                    f"💡 **Copilot Recommendation**: {owns_text} "
                )
                
                if trend == "BULLISH":
                    if rsi > 65:
                        analysis += "The stock is showing strong bullish momentum but entering overbought territory. It is recommended to hold or buy on temporary pullbacks."
                    else:
                        analysis += "The technical setup is highly favorable with active upward momentum. Good accumulation window."
                else:
                    if rsi < 35:
                        analysis += "The stock is in a downtrend but technically oversold. It represents a potential value-buy opportunity for long-term compounding."
                    else:
                        analysis += "The stock is consolidating or correcting. It is recommended to wait for trend reversal confirmation before initiating new positions."
                return analysis

        # intent: portfolio summary / analytics
        if any(x in msg_lower for x in ["portfolio", "holding", "investment", "shares"]):
            if not portfolio_summary:
                return "Your portfolio is currently empty. Go to the Portfolio page to add some holdings and get a detailed analytics breakdown!"
                
            total_value = sum(h["value"] for h in portfolio_summary)
            holdings_list = "\n".join([f"* **{h['symbol']}**: {h['qty']} shares @ ₹{h['current_price']} (Value: ₹{h['value']})" for h in portfolio_summary])
            
            # Fetch analytics
            analytics = PortfolioService.get_portfolio_analytics(str(user_id))
            summary = analytics["summary"]
            metrics = analytics["metrics"]
            
            response = (
                f"### 💼 Portfolio Analytics Summary\n"
                f"Here is a summary of your active investments:\n\n"
                f"{holdings_list}\n\n"
                f"**Financial Overview**:\n"
                f"* **Total Investment**: ₹{summary['total_investment']}\n"
                f"* **Current Value**: ₹{summary['total_current_value']}\n"
                f"* **Total Returns**: ₹{summary['total_gain_loss']} ({summary['total_gain_loss_pct']}%)\n\n"
                f"**Risk Profile**:\n"
                f"* **Portfolio Beta**: {metrics['portfolio_beta']} (Market benchmark is 1.0)\n"
                f"* **Sharpe Ratio**: {metrics['sharpe_ratio']} (Reward per unit of risk)\n"
                f"* **Diversification Score**: {metrics['diversification_score']}/100\n\n"
                f"💡 **Rebalancing Suggestion**: {analytics['advice']}"
            )
            return response

        # intent: watchlist
        if "watchlist" in msg_lower:
            if not watchlist_summary:
                return "Your watchlist is currently empty. Star some stocks from the search or dashboard to keep track of them here!"
            
            watchlist_details = []
            for symbol in watchlist_summary:
                signals = AdvisorService._fetch_signals(symbol)
                price_str = f"₹{signals['current_price']}" if signals else "N/A"
                trend_str = "📈 BULLISH" if signals and signals.get("trend") == "BULLISH" else "📉 BEARISH"
                watchlist_details.append(f"* **{symbol}**: {price_str} ({trend_str})")
                
            return (
                f"### ⭐ Your Watchlist\n"
                f"Here are the stocks you are currently tracking:\n\n"
                f"\n".join(watchlist_details) + "\n\n"
                f"You can add alerts for any of these stocks to be notified when they cross target prices."
            )

        # intent: risk / Beta / VaR
        if any(x in msg_lower for x in ["risk", "beta", "sharpe", "volatility", "var"]):
            analytics = PortfolioService.get_portfolio_analytics(str(user_id))
            metrics = analytics["metrics"]
            summary = analytics["summary"]
            
            return (
                f"### 🛡️ Risk & Volatility Dashboard\n"
                f"Here are the risk parameters computed for your portfolio:\n\n"
                f"* **Diversification Score**: **{metrics['diversification_score']}/100**\n"
                f"* **Weighted Portfolio Beta**: **{metrics['portfolio_beta']}** (values > 1.0 indicate higher volatility than the index)\n"
                f"* **Portfolio Annual Volatility**: **{metrics['portfolio_volatility_annual']}%**\n"
                f"* **Sharpe Ratio**: **{metrics['sharpe_ratio']}**\n"
                f"* **Value at Risk (VaR 95% - 1 Day)**: **₹{metrics['value_at_risk_95']}** (expected maximum loss over a 24h period under standard conditions)\n\n"
                f"💡 **Risk Management Advice**: {analytics['advice']}"
            )

        # intent: recommendations / advisor
        if any(x in msg_lower for x in ["recommend", "buy", "picks", "suggest", "advisor"]):
            return (
                "### 🎯 AI Investment Recommendations\n"
                "I can analyze your goals to suggest stocks. You can access the **AI Advisor** tab for complete allocations, "
                "or tell me about your goals (e.g., *wealth creation*, *stable dividends*, or *retirement planning*) and risk tolerance, "
                "and I will outline matching tickers."
            )

        # Default fallback / Greeting
        return (
            "👋 **Hello! I'm Invexo Copilot, your AI investment assistant.**\n\n"
            "Here's what you can ask me:\n"
            "* 💼 **Show my portfolio summary** - Get allocations, total value, and returns.\n"
            "* 🛡️ **Analyze my portfolio risk** - View Beta, Volatility, and Value at Risk.\n"
            "* 📊 **Analyze [SYMBOL]** - Get live technical indicators for any stock (e.g. *Analyze RELIANCE*).\n"
            "* ⭐ **Show my watchlist** - View all stocks you are currently tracking.\n\n"
            "How can I help you with your investments today?"
        )
