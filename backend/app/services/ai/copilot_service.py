from app.repositories.portfolio_repository import PortfolioRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.market.advisor_service import AdvisorService, UNIVERSE
from app.services.market.ticker_utils import _working_ticker
from app.services.portfolio.portfolio_service import PortfolioService
from app.services.ai.copilot_tools import TOOL_DECLARATIONS, WRITE_TOOLS, execute_tool
from app.utils.logger import get_logger
import os
import requests

logger = get_logger("copilot_service")

# Gemini model powering Vexo. Override with GEMINI_MODEL env var.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip()
# Safety cap on function-calling rounds per user message.
MAX_TOOL_ROUNDS = 6

SYSTEM_INSTRUCTION = (
    "You are Vexo, the built-in AI assistant for Invexo — a modern Indian stock-market "
    "analytics platform. You have real, live access to the platform through tools and you "
    "should use them freely to give accurate, data-backed answers instead of guessing.\n\n"
    "Capabilities available to you via tools:\n"
    "- Run the ML prediction model for any stock (get_stock_prediction) — use this whenever "
    "the user asks for a prediction, forecast, price target, or outlook on a stock.\n"
    "- Live snapshots, stock news, and general market news.\n"
    "- Today's AI 'Daily Edge' picks and tailored AI Advisor recommendations.\n"
    "- Read the user's own portfolio (with analytics) and watchlist.\n"
    "- Take actions for the user: create/delete price alerts, add/remove watchlist items, "
    "add/remove portfolio holdings, and run the investment growth calculator.\n\n"
    "Guidelines:\n"
    "- Prefer calling a tool over answering from memory for anything involving live prices, "
    "predictions, the user's data, news, or picks.\n"
    "- Indian stocks use NSE symbols without a suffix (e.g. RELIANCE, TCS, INFY).\n"
    "- Before taking a destructive or money-related action (adding/removing a holding, "
    "deleting an alert), make sure the user clearly asked for it; confirm details like "
    "quantity and price if they're ambiguous.\n"
    "- When you present a prediction, briefly note the current price, the predicted price, "
    "the confidence, and the key driver — and remind the user it's a model estimate, not "
    "guaranteed. Keep disclaimers light; don't repeat them every sentence.\n"
    "- Respond in clean, concise GitHub-flavored markdown with headings, bullet points and "
    "bold figures where it helps readability. Use ₹ for prices."
)


class CopilotService:
    @staticmethod
    def get_copilot_response(user_id: int, message: str, history: list | None = None) -> str:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if api_key:
            try:
                answer = CopilotService._run_agent(user_id, message, history or [], api_key)
                if answer:
                    return answer
            except Exception as e:
                logger.error(f"Vexo agent failed, using fallback: {e}")
        # Offline / failure fallback: rule-based engine.
        return CopilotService._fallback_response(user_id, message)

    # ── Gemini tool-calling agent ──────────────────────────────────────────
    @staticmethod
    def _build_contents(message: str, history: list) -> list:
        """Convert stored chat history + the new message into Gemini `contents`."""
        contents = []
        for turn in (history or [])[-10:]:
            sender = turn.get("sender")
            text = (turn.get("text") or "").strip()
            if not text:
                continue
            role = "user" if sender == "user" else "model"
            contents.append({"role": role, "parts": [{"text": text}]})
        contents.append({"role": "user", "parts": [{"text": message}]})
        return contents

    @staticmethod
    def _run_agent(user_id: int, message: str, history: list, api_key: str) -> str:
        api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent?key={api_key}"
        )
        headers = {"Content-Type": "application/json"}
        contents = CopilotService._build_contents(message, history)

        base_payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "tools": [{"function_declarations": TOOL_DECLARATIONS}],
            "generationConfig": {"temperature": 0.4},
        }

        for _ in range(MAX_TOOL_ROUNDS):
            payload = {**base_payload, "contents": contents}
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            if response.status_code != 200:
                logger.error(f"Gemini API error {response.status_code}: {response.text[:500]}")
                return ""

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            candidate_content = candidates[0].get("content", {}) or {}
            parts = candidate_content.get("parts", []) or []

            function_calls = [p["functionCall"] for p in parts if p.get("functionCall")]

            if not function_calls:
                # No tool requested → this is the final natural-language answer.
                text = "".join(p.get("text", "") for p in parts).strip()
                return text

            # Record the model's tool-call turn, then execute each call and
            # append the results so the model can continue.
            contents.append({"role": candidate_content.get("role", "model"), "parts": parts})

            response_parts = []
            for call in function_calls:
                name = call.get("name", "")
                args = call.get("args", {}) or {}
                if name in WRITE_TOOLS:
                    logger.info(f"[Vexo] User {user_id} write-action via '{name}': {args}")
                result = execute_tool(user_id, name, args)
                response_parts.append({
                    "functionResponse": {"name": name, "response": {"result": result}}
                })
            contents.append({"role": "user", "parts": response_parts})

        logger.warning(f"[Vexo] Hit MAX_TOOL_ROUNDS for user {user_id}")
        return (
            "I gathered a lot of data but couldn't quite wrap up — could you narrow the "
            "question down a little?"
        )

    # ── Rule-based fallback (used only when Gemini is unavailable) ──────────
    @staticmethod
    def _fallback_response(user_id: int, message: str) -> str:
        holdings = PortfolioRepository.get_portfolio(user_id)
        watchlist = WatchlistRepository.get_watchlist(user_id)

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
                "value": round(h["quantity"] * price, 2),
            })

        watchlist_summary = [w["symbol"] for w in watchlist]
        msg_lower = message.lower()

        # Specific stock analysis
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

                user_owns = False
                owned_qty = 0.0
                for h in portfolio_summary:
                    if h["symbol"].upper() == symbol.upper():
                        user_owns = True
                        owned_qty = h["qty"]

                owns_text = f"You currently hold **{owned_qty} shares** of {symbol} in your portfolio." if user_owns else f"You do not currently hold {symbol} in your portfolio."
                rsi_status = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"

                analysis = (
                    f"### 📊 Technical Analysis for **{symbol}** ({meta.get('name', '')})\n"
                    f"*{meta.get('desc', '')}*\n\n"
                    f"* **Current Price**: ₹{price}\n"
                    f"* **Trend**: 📈 {trend} momentum\n"
                    f"* **RSI (14-day)**: {rsi} ({rsi_status} conditions)\n"
                    f"* **Sector**: {meta.get('sector', 'Other')}\n"
                    f"* **Risk Profile**: {meta.get('risk', 'medium')}\n\n"
                    f"💡 **Vexo Recommendation**: {owns_text} "
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

        if any(x in msg_lower for x in ["portfolio", "holding", "investment", "shares"]):
            if not portfolio_summary:
                return "Your portfolio is currently empty. Go to the Portfolio page to add some holdings and get a detailed analytics breakdown!"

            holdings_list = "\n".join([f"* **{h['symbol']}**: {h['qty']} shares @ ₹{h['current_price']} (Value: ₹{h['value']})" for h in portfolio_summary])
            analytics = PortfolioService.get_portfolio_analytics(str(user_id))
            summary = analytics["summary"]
            metrics = analytics["metrics"]

            return (
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

        if any(x in msg_lower for x in ["risk", "beta", "sharpe", "volatility", "var"]):
            analytics = PortfolioService.get_portfolio_analytics(str(user_id))
            metrics = analytics["metrics"]
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

        if any(x in msg_lower for x in ["recommend", "buy", "picks", "suggest", "advisor"]):
            return (
                "### 🎯 AI Investment Recommendations\n"
                "I can analyze your goals to suggest stocks. You can access the **AI Advisor** tab for complete allocations, "
                "or tell me about your goals (e.g., *wealth creation*, *stable dividends*, or *retirement planning*) and risk tolerance, "
                "and I will outline matching tickers."
            )

        return (
            "👋 **Hello! I'm Vexo, your AI investment assistant.**\n\n"
            "Here's what you can ask me:\n"
            "* 📈 **Predict [SYMBOL]** - Run the AI model for a price forecast (e.g. *Predict RELIANCE*).\n"
            "* 💼 **Show my portfolio summary** - Get allocations, total value, and returns.\n"
            "* 🛡️ **Analyze my portfolio risk** - View Beta, Volatility, and Value at Risk.\n"
            "* 📊 **Analyze [SYMBOL]** - Get live technical indicators for any stock.\n"
            "* ⭐ **Show my watchlist** - View all stocks you are currently tracking.\n\n"
            "How can I help you with your investments today?"
        )
