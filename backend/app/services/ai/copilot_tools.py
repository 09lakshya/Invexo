"""
Tool registry for Vexo, the AI assistant.

Each tool wraps an existing Invexo service so Vexo can actually *use* the
platform — run ML predictions, read live market data, inspect the user's
portfolio/watchlist, and take actions (alerts, watchlist, holdings) on their
behalf. The module exposes:

  * TOOL_DECLARATIONS  — Gemini function-declaration schemas (the tool "menu")
  * execute_tool(...)  — dispatches a tool call to the right service and
                         returns a compact, JSON-serialisable result.

Tools that mutate user data are marked in TOOL_DECLARATIONS via the WRITE_TOOLS
set so the caller/UI can reason about them if needed.
"""
from app.utils.logger import get_logger

logger = get_logger("copilot_tools")

# Tools that change user state (used for logging / awareness).
WRITE_TOOLS = {
    "create_price_alert",
    "delete_price_alert",
    "add_to_watchlist",
    "remove_from_watchlist",
    "add_portfolio_holding",
    "remove_portfolio_holding",
}

# ── Gemini function declarations ────────────────────────────────────────────
# JSON-schema "parameters" follow the OpenAPI subset Gemini accepts.
TOOL_DECLARATIONS = [
    {
        "name": "get_stock_prediction",
        "description": (
            "Run Invexo's machine-learning prediction model (XGBoost + technical, "
            "sentiment and fundamental signals) for a single stock. Use this whenever "
            "the user asks for a prediction, forecast, price target, or 'where is X "
            "headed'. Returns current price, predicted price, ML (xgb) predicted price, "
            "day-close prediction, confidence %, trend, RSI, MACD, volatility, news "
            "sentiment and a short explanation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "NSE ticker symbol, e.g. 'RELIANCE', 'TCS', 'INFY'. Without exchange suffix.",
                }
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_stock_snapshot",
        "description": (
            "Quick live snapshot of a stock: current price, 14-day RSI and short-term "
            "trend (BULLISH/BEARISH). Faster and lighter than a full prediction — use "
            "for 'what's the price of X' or a quick technical read."
        ),
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "NSE ticker symbol, e.g. 'WIPRO'."}},
            "required": ["symbol"],
        },
    },
    {
        "name": "get_stock_news",
        "description": "Latest news headlines for a specific stock, with publisher and date.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "NSE ticker symbol."}},
            "required": ["symbol"],
        },
    },
    {
        "name": "get_market_news",
        "description": "Top general Indian market / financial news headlines right now (not stock-specific).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_daily_picks",
        "description": (
            "Invexo's 'Daily Edge' — today's AI-ranked top stock picks from the "
            "cross-sectional ranking model, with expected 5-day move, model confidence "
            "and reasoning. Use when the user asks for today's picks, best stocks today, "
            "or the Daily Edge."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_investment_recommendations",
        "description": (
            "Invexo AI Advisor: builds a tailored basket of stock recommendations with "
            "suggested allocations for a user's goal, horizon, risk appetite and budget. "
            "Use when the user asks 'what should I invest in', 'suggest stocks for me', "
            "retirement/wealth/income planning, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Investment goal.",
                    "enum": ["wealth", "income", "retirement", "education", "safety"],
                },
                "duration": {
                    "type": "string",
                    "description": "Time horizon.",
                    "enum": ["short", "medium", "long"],
                },
                "risk": {
                    "type": "string",
                    "description": "Risk tolerance.",
                    "enum": ["low", "medium", "high"],
                },
                "budget": {
                    "type": "number",
                    "description": "Investment amount in INR. For SIP, the per-month amount.",
                },
                "investment_type": {
                    "type": "string",
                    "description": "One-time lumpsum or recurring monthly SIP.",
                    "enum": ["one-time", "monthly"],
                },
                "investment_months": {
                    "type": "integer",
                    "description": "For SIP only: number of months. Optional.",
                },
            },
            "required": ["goal", "duration", "risk", "budget"],
        },
    },
    {
        "name": "get_portfolio",
        "description": (
            "The signed-in user's portfolio: holdings with live prices plus full "
            "analytics — total investment, current value, gain/loss, beta, Sharpe ratio, "
            "volatility, Value at Risk, diversification score and rebalancing advice."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_watchlist",
        "description": "The user's watchlist with a live price/trend snapshot for each tracked stock.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "list_price_alerts",
        "description": "List the user's price alerts (both active and already-triggered).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "create_price_alert",
        "description": (
            "Create a price alert for the user. When the stock crosses the target the "
            "user is emailed automatically. Use for 'notify/alert me when X goes above/below Y'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "NSE ticker symbol."},
                "target_price": {"type": "number", "description": "Target price in INR (must be > 0)."},
                "condition": {
                    "type": "string",
                    "description": "Trigger when price goes 'above' or 'below' the target.",
                    "enum": ["above", "below"],
                },
            },
            "required": ["symbol", "target_price", "condition"],
        },
    },
    {
        "name": "delete_price_alert",
        "description": "Delete one of the user's price alerts by its id (get ids from list_price_alerts).",
        "parameters": {
            "type": "object",
            "properties": {"alert_id": {"type": "integer", "description": "Alert id to delete."}},
            "required": ["alert_id"],
        },
    },
    {
        "name": "add_to_watchlist",
        "description": "Add a stock to the user's watchlist.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "NSE ticker symbol."}},
            "required": ["symbol"],
        },
    },
    {
        "name": "remove_from_watchlist",
        "description": "Remove a stock from the user's watchlist.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "NSE ticker symbol."}},
            "required": ["symbol"],
        },
    },
    {
        "name": "add_portfolio_holding",
        "description": (
            "Add a holding to the user's portfolio. Confirm quantity and buy price with "
            "the user before calling — this records a real position."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "NSE ticker symbol."},
                "quantity": {"type": "number", "description": "Number of shares."},
                "buy_price": {"type": "number", "description": "Average buy price per share in INR."},
                "company_name": {"type": "string", "description": "Optional company name."},
            },
            "required": ["symbol", "quantity", "buy_price"],
        },
    },
    {
        "name": "remove_portfolio_holding",
        "description": "Remove a holding from the user's portfolio by its holding id (get ids from get_portfolio).",
        "parameters": {
            "type": "object",
            "properties": {"holding_id": {"type": "integer", "description": "Holding id to remove."}},
            "required": ["holding_id"],
        },
    },
    {
        "name": "calculate_investment_growth",
        "description": (
            "Project the future value of a lump-sum investment using compound growth, "
            "including an inflation-adjusted real return. Use for 'if I invest X at Y% "
            "for Z years, what will it be worth'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "principal": {"type": "number", "description": "Amount invested in INR."},
                "annual_rate": {"type": "number", "description": "Expected annual return as a fraction, e.g. 0.12 for 12%."},
                "years": {"type": "integer", "description": "Number of years."},
                "inflation_rate": {"type": "number", "description": "Annual inflation as a fraction (default 0.06)."},
            },
            "required": ["principal", "annual_rate", "years"],
        },
    },
]


def _clean_symbol(symbol: str) -> str:
    return (symbol or "").upper().strip().replace(".NS", "").replace(".BO", "")


# ── Dispatcher ──────────────────────────────────────────────────────────────
def execute_tool(user_id: int, name: str, args: dict) -> dict:
    """
    Execute a single tool call and return a JSON-serialisable dict.
    Never raises — errors come back as {"error": "..."} so the model can recover.
    """
    args = args or {}
    try:
        if name == "get_stock_prediction":
            from app.services.ai.prediction_service import PredictionService
            symbol = _clean_symbol(args.get("symbol", ""))
            if not symbol:
                return {"error": "A stock symbol is required."}
            res = PredictionService.predict_stock(symbol)
            if "error" in res:
                return {"error": res["error"], "symbol": symbol}
            return {
                "symbol": symbol,
                "current_price": res.get("current_price"),
                "percent_change_today": res.get("percent_change"),
                "ml_predicted_price": res.get("xgb_predicted_price") or res.get("prediction"),
                "heuristic_predicted_price": res.get("predicted_price"),
                "day_close_prediction": res.get("day_close_prediction"),
                "confidence_pct": res.get("confidence"),
                "trend": res.get("trend"),
                "rsi": res.get("rsi"),
                "macd": res.get("macd"),
                "volatility_pct": res.get("volatility"),
                "news_sentiment": res.get("news_sentiment"),
                "fundamental_score": res.get("fundamental_score"),
                "pe_ratio": res.get("pe_ratio"),
                "explanation": res.get("explanation", {}).get("summary"),
            }

        if name == "get_stock_snapshot":
            from app.services.market.advisor_service import AdvisorService
            symbol = _clean_symbol(args.get("symbol", ""))
            if not symbol:
                return {"error": "A stock symbol is required."}
            signals = AdvisorService._fetch_signals(symbol)
            if not signals:
                return {"error": f"No live data available for {symbol}.", "symbol": symbol}
            return {"symbol": symbol, **signals}

        if name == "get_stock_news":
            from app.services.market.news_service import NewsService
            symbol = _clean_symbol(args.get("symbol", ""))
            if not symbol:
                return {"error": "A stock symbol is required."}
            news = NewsService.get_stock_news(symbol) or []
            return {"symbol": symbol, "news": news[:5]}

        if name == "get_market_news":
            from app.services.market.general_news_service import GeneralNewsService
            news = GeneralNewsService.get_general_news() or []
            trimmed = [
                {"title": n.get("title"), "date": n.get("date"),
                 "link": n.get("link"), "summary": n.get("summary")}
                for n in news[:6]
            ]
            return {"news": trimmed}

        if name == "get_daily_picks":
            from app.services.market.market_service import MarketService
            picks = MarketService.get_daily_picks()
            if picks is None:
                return {"status": "updating", "message": "The AI is still analysing the market for today's picks."}
            slim = [
                {"symbol": p.get("symbol"), "current_price": p.get("current_price"),
                 "target_price": p.get("target_price"), "expected_5d_pct": p.get("expected_5d_pct"),
                 "confidence": p.get("confidence"), "signal_1d": p.get("signal_1d"),
                 "reasoning": p.get("reasoning")}
                for p in picks[:10]
            ]
            return {"status": "ready", "picks": slim}

        if name == "get_investment_recommendations":
            from app.services.market.advisor_service import AdvisorService
            recs = AdvisorService.get_recommendations(
                goal=args.get("goal", "wealth"),
                duration=args.get("duration", "medium"),
                risk=args.get("risk", "medium"),
                budget=float(args.get("budget", 0) or 0),
                investment_type=args.get("investment_type", "one-time"),
                investment_months=args.get("investment_months"),
            )
            slim = [
                {"symbol": r.get("symbol"), "name": r.get("name"), "sector": r.get("sector"),
                 "risk_level": r.get("risk_level"), "current_price": r.get("current_price"),
                 "confidence": r.get("confidence"), "suggested_allocation": r.get("suggested_allocation"),
                 "shares_you_can_buy": r.get("shares_you_can_buy"), "reason": r.get("reason")}
                for r in recs
            ]
            return {"recommendations": slim}

        if name == "get_portfolio":
            from app.services.portfolio.portfolio_service import PortfolioService
            from app.repositories.portfolio_repository import PortfolioRepository
            holdings = PortfolioRepository.get_portfolio(str(user_id))
            analytics = PortfolioService.get_portfolio_analytics(str(user_id))
            return {
                "holdings": [
                    {"id": h.get("id"), "symbol": h.get("symbol"), "company_name": h.get("company_name"),
                     "quantity": h.get("quantity"), "buy_price": h.get("buy_price")}
                    for h in holdings
                ],
                "summary": analytics.get("summary"),
                "metrics": analytics.get("metrics"),
                "allocations": analytics.get("allocations"),
                "advice": analytics.get("advice"),
            }

        if name == "get_watchlist":
            from app.repositories.watchlist_repository import WatchlistRepository
            from app.services.market.advisor_service import AdvisorService
            watchlist = WatchlistRepository.get_watchlist(user_id)
            items = []
            for w in watchlist:
                sym = w["symbol"]
                sig = AdvisorService._fetch_signals(sym)
                items.append({
                    "symbol": sym,
                    "current_price": sig.get("current_price") if sig else None,
                    "rsi": sig.get("rsi") if sig else None,
                    "trend": sig.get("trend") if sig else None,
                })
            return {"watchlist": items}

        if name == "list_price_alerts":
            from app.repositories.alert_repository import AlertRepository
            alerts = AlertRepository.get_user_alerts(user_id)
            return {"alerts": [
                {"id": a.get("id"), "symbol": a.get("symbol"), "target_price": a.get("target_price"),
                 "condition": a.get("condition"), "is_active": a.get("is_active"),
                 "triggered_at": a.get("triggered_at")}
                for a in alerts
            ]}

        if name == "create_price_alert":
            from app.repositories.alert_repository import AlertRepository
            symbol = _clean_symbol(args.get("symbol", ""))
            target_price = float(args.get("target_price", 0) or 0)
            condition = str(args.get("condition", "")).lower().strip()
            if not symbol or target_price <= 0 or condition not in ("above", "below"):
                return {"error": "Need a valid symbol, a target price > 0, and condition 'above' or 'below'."}
            new_id = AlertRepository.create_alert(user_id, symbol, target_price, condition)
            if new_id is None:
                return {"error": "Failed to create the alert."}
            return {"success": True, "alert_id": new_id,
                    "message": f"Alert set for {symbol} when price goes {condition} ₹{target_price}."}

        if name == "delete_price_alert":
            from app.repositories.alert_repository import AlertRepository
            alert_id = int(args.get("alert_id"))
            ok = AlertRepository.delete_alert(user_id, alert_id)
            return {"success": ok} if ok else {"error": "Alert not found or not yours."}

        if name == "add_to_watchlist":
            from app.repositories.watchlist_repository import WatchlistRepository
            symbol = _clean_symbol(args.get("symbol", ""))
            if not symbol:
                return {"error": "A stock symbol is required."}
            ok = WatchlistRepository.add_to_watchlist(user_id, symbol)
            return {"success": ok, "symbol": symbol} if ok else {"error": f"Could not add {symbol} (maybe already on your watchlist)."}

        if name == "remove_from_watchlist":
            from app.repositories.watchlist_repository import WatchlistRepository
            symbol = _clean_symbol(args.get("symbol", ""))
            ok = WatchlistRepository.remove_from_watchlist(user_id, symbol)
            return {"success": ok, "symbol": symbol} if ok else {"error": f"{symbol} was not on your watchlist."}

        if name == "add_portfolio_holding":
            from app.services.portfolio.portfolio_service import PortfolioService
            symbol = _clean_symbol(args.get("symbol", ""))
            quantity = float(args.get("quantity", 0) or 0)
            buy_price = float(args.get("buy_price", 0) or 0)
            if not symbol or quantity <= 0 or buy_price <= 0:
                return {"error": "Need a symbol, quantity > 0 and buy price > 0."}
            company_name = args.get("company_name") or symbol
            hid = PortfolioService.add_holding(str(user_id), symbol, company_name, quantity, buy_price)
            if hid is None:
                return {"error": "Failed to add the holding."}
            return {"success": True, "holding_id": hid,
                    "message": f"Added {quantity} shares of {symbol} at ₹{buy_price}."}

        if name == "remove_portfolio_holding":
            from app.services.portfolio.portfolio_service import PortfolioService
            holding_id = int(args.get("holding_id"))
            ok = PortfolioService.remove_holding(holding_id, str(user_id))
            return {"success": ok} if ok else {"error": "Holding not found or not yours."}

        if name == "calculate_investment_growth":
            from app.services.calculator.calculator_service import CalculatorService
            return CalculatorService.calculate_investment(
                principal=float(args.get("principal", 0) or 0),
                annual_rate=float(args.get("annual_rate", 0) or 0),
                years=int(args.get("years", 0) or 0),
                inflation_rate=float(args.get("inflation_rate", 0.06) if args.get("inflation_rate") is not None else 0.06),
            )

        return {"error": f"Unknown tool '{name}'."}
    except Exception as e:
        logger.error(f"Tool '{name}' failed: {e}")
        return {"error": f"Tool '{name}' failed: {e}"}
