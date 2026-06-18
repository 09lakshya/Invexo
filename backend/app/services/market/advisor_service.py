import yfinance as yf
import numpy as np
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from app.services.market.ticker_utils import _yf_session, _working_ticker, _ticker_candidates, ttl_cache
from app.core.redis import redis_client

UNIVERSE = {
    "HDFCBANK.NS":   {"name": "HDFC Bank",            "sector": "Banking",         "risk": "low",    "desc": "India's largest private bank — safe, stable, and consistently profitable."},
    "TCS.NS":        {"name": "TCS",                   "sector": "IT",              "risk": "low",    "desc": "Tata's IT giant that runs software for companies across 46 countries."},
    "INFY.NS":       {"name": "Infosys",               "sector": "IT",              "risk": "low",    "desc": "One of India's most trusted software exporters with a global client base."},
    "ITC.NS":        {"name": "ITC",                   "sector": "FMCG",            "risk": "low",    "desc": "Behind brands like Aashirvaad, Classmate, and Fiama — strong cash flows."},
    "HINDUNILVR.NS": {"name": "Hindustan Unilever",    "sector": "FMCG",            "risk": "low",    "desc": "Maker of Dove, Lifebuoy, Surf Excel — products in every Indian household."},
    "NESTLEIND.NS":  {"name": "Nestle India",          "sector": "FMCG",            "risk": "low",    "desc": "Behind Maggi and KitKat — a premium FMCG stock with consistent profits."},
    "RELIANCE.NS":   {"name": "Reliance Industries",   "sector": "Conglomerate",    "risk": "medium", "desc": "India's largest company, spanning oil & gas, Jio, and retail."},
    "BHARTIARTL.NS": {"name": "Bharti Airtel",         "sector": "Telecom",         "risk": "medium", "desc": "India's #2 telecom company, riding the 5G growth wave."},
    "AXISBANK.NS":   {"name": "Axis Bank",             "sector": "Banking",         "risk": "medium", "desc": "One of India's top private banks with a strong digital banking platform."},
    "WIPRO.NS":      {"name": "Wipro",                 "sector": "IT",              "risk": "medium", "desc": "A global IT services company with a growing focus on AI and cloud."},
    "HCLTECH.NS":    {"name": "HCL Technologies",      "sector": "IT",              "risk": "medium", "desc": "Fast-growing IT company known for engineering and product services."},
    "BAJFINANCE.NS": {"name": "Bajaj Finance",         "sector": "Finance",         "risk": "medium", "desc": "India's largest consumer-finance company — strong growth, wide reach."},
    "TMPV.NS":       {"name": "Tata Motors Passenger", "sector": "Auto",            "risk": "medium", "desc": "Maker of Tata EVs and passenger vehicles post-demerger."},
    "ADANIENT.NS":   {"name": "Adani Enterprises",     "sector": "Infrastructure",  "risk": "high",   "desc": "India's largest infrastructure conglomerate — high growth potential, higher risk."},
    "SUZLON.NS":     {"name": "Suzlon Energy",         "sector": "Renewable Energy","risk": "high",   "cap": "small", "desc": "Leading wind energy company riding India's green-energy push."},
    "IDFCFIRSTB.NS": {"name": "IDFC First Bank",       "sector": "Banking",         "risk": "medium", "cap": "mid",   "desc": "A challenger private bank with retail-led growth and improving operating metrics."},
    "IRFC.NS":       {"name": "IRFC",                  "sector": "Finance",         "risk": "medium", "cap": "mid",   "desc": "Railway financing company linked to India's long-term rail infrastructure expansion."},
    "NHPC.NS":       {"name": "NHPC",                  "sector": "Power",           "risk": "medium", "cap": "mid",   "desc": "Hydropower utility with public-sector backing and renewable-energy optionality."},
    "IDEA.NS":       {"name": "Vodafone Idea",         "sector": "Telecom",         "risk": "high",   "cap": "penny", "desc": "A speculative telecom turnaround candidate with survival and debt-related risks."},
    "YESBANK.NS":    {"name": "Yes Bank",              "sector": "Banking",         "risk": "high",   "cap": "penny", "desc": "A recovering private bank; suitable only for investors who can tolerate high uncertainty."},
    "JPPOWER.NS":    {"name": "Jaiprakash Power",      "sector": "Power",           "risk": "high",   "cap": "penny", "desc": "Power-sector penny stock with turnaround potential and meaningful balance-sheet risk."},
    "RPOWER.NS":     {"name": "Reliance Power",        "sector": "Power",           "risk": "high",   "cap": "penny", "desc": "Speculative power-sector name where price action can be sharp and unpredictable."},
    "GMRAIRPORT.NS": {"name": "GMR Airports Infra",    "sector": "Infrastructure",  "risk": "high",   "cap": "small", "desc": "Airport infrastructure operator with traffic-growth upside and elevated execution risk."},
    "SOUTHBANK.NS":  {"name": "South Indian Bank",     "sector": "Banking",         "risk": "high",   "cap": "penny", "desc": "Regional bank turnaround idea with lower valuation and higher asset-quality sensitivity."},
    "UJJIVANSFB.NS": {"name": "Ujjivan Small Finance", "sector": "Banking",         "risk": "high",   "cap": "small", "desc": "Small finance bank exposed to inclusion-led growth, but with cyclical credit risk."},
    "IFCI.NS":       {"name": "IFCI",                  "sector": "Finance",         "risk": "high",   "cap": "penny", "desc": "Speculative financial-services name where momentum can dominate fundamentals."},
    "PATELENG.NS":   {"name": "Patel Engineering",     "sector": "Infrastructure",  "risk": "high",   "cap": "small", "desc": "Infrastructure contractor that can benefit from capex cycles, with execution risk."},
    "GTLINFRA.NS":   {"name": "GTL Infrastructure",    "sector": "Telecom Infra",   "risk": "high",   "cap": "penny", "desc": "Very speculative telecom-infrastructure penny stock with extreme volatility."},
}

GOAL_CANDIDATES = {
    "wealth":     ["RELIANCE.NS", "HCLTECH.NS", "BHARTIARTL.NS", "BAJFINANCE.NS",
                   "TMPV.NS", "ADANIENT.NS", "WIPRO.NS", "SUZLON.NS",
                   "GMRAIRPORT.NS", "PATELENG.NS", "IDEA.NS", "JPPOWER.NS"],
    "income":     ["ITC.NS", "HINDUNILVR.NS", "NESTLEIND.NS",
                   "HDFCBANK.NS", "TCS.NS", "INFY.NS", "NHPC.NS", "IRFC.NS"],
    "retirement": ["HDFCBANK.NS", "TCS.NS", "HINDUNILVR.NS",
                   "ITC.NS", "NESTLEIND.NS", "INFY.NS"],
    "education":  ["HDFCBANK.NS", "TCS.NS", "RELIANCE.NS",
                   "BAJFINANCE.NS", "BHARTIARTL.NS", "INFY.NS", "IDFCFIRSTB.NS", "IRFC.NS"],
    "safety":     ["HDFCBANK.NS", "TCS.NS", "HINDUNILVR.NS",
                   "ITC.NS", "NESTLEIND.NS"],
}

DURATION_LABELS = {
    "short":  "under 1 year",
    "medium": "1–3 years",
    "long":   "3+ years",
}

TARGET_STOCKS_BY_DURATION = {
    "short": 3,
    "medium": 6,
    "long": 10,
}

DEFAULT_MONTHS_BY_DURATION = {
    "short": 12,
    "medium": 36,
    "long": 60,
}

RISK_COMPATIBILITY = {
    "low": {"low"},
    "medium": {"low", "medium"},
    "high": {"low", "medium", "high"},
}

DURATION_MULTIPLIERS = {
    "short":  {"low": 1.2, "medium": 0.9, "high": 0.7},
    "medium": {"low": 1.0, "medium": 1.1, "high": 0.9},
    "long":   {"low": 0.8, "medium": 0.9, "high": 1.3},
}

class AdvisorService:
    @staticmethod
    def _rsi(prices, period=14):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _analyze_sentiment(text):
        if not text:
            return 50
        try:
            from textblob import TextBlob
            blob = TextBlob(str(text))
            polarity = blob.sentiment.polarity
            return (polarity + 1) * 50
        except Exception:
            return 50

    @staticmethod
    def _advisor_candidates(goal: str, risk: str):
        goal_matches = GOAL_CANDIDATES.get(goal, GOAL_CANDIDATES["wealth"])
        allowed_risks = RISK_COMPATIBILITY.get(risk, {"low", "medium"})
        compatible_universe = [
            sym for sym, meta in UNIVERSE.items()
            if meta.get("risk", "medium") in allowed_risks
        ]
        prioritized = [sym for sym in goal_matches if sym in compatible_universe]
        return prioritized + [sym for sym in compatible_universe if sym not in prioritized]

    @staticmethod
    def _is_opportunistic(meta: dict) -> bool:
        return meta.get("cap") in {"small", "micro", "penny"}

    @staticmethod
    def _opportunistic_bonus(meta: dict, goal: str, duration: str, risk: str) -> int:
        if not AdvisorService._is_opportunistic(meta):
            return 0
        bonus = 0
        if risk == "high": bonus += 14
        if goal == "wealth": bonus += 8
        if duration == "long": bonus += 8
        elif duration == "medium": bonus += 3
        else: bonus -= 6
        if goal in {"safety", "retirement"}: bonus -= 18
        if risk == "low": bonus -= 25
        return bonus

    @staticmethod
    def _minimum_opportunistic_count(goal: str, duration: str, risk: str, target_count: int) -> int:
        if risk != "high": return 0
        if duration == "long" and target_count >= 6: return 2
        if goal == "wealth" or duration in {"medium", "long"}: return 1
        return 0

    @staticmethod
    def _select_recommendations(scored: list, goal: str, duration: str, risk: str, target_count: int):
        selected = scored[:target_count]
        needed = AdvisorService._minimum_opportunistic_count(goal, duration, risk, target_count)
        if needed <= 0:
            return selected

        selected_symbols = {item["sym"] for item in selected}
        current_count = sum(1 for item in selected if AdvisorService._is_opportunistic(item["meta"]))
        replacements = [
            item for item in scored
            if item["sym"] not in selected_symbols and AdvisorService._is_opportunistic(item["meta"])
        ]

        while current_count < needed and replacements and selected:
            replacement = replacements.pop(0)
            for idx in range(len(selected) - 1, -1, -1):
                if not AdvisorService._is_opportunistic(selected[idx]["meta"]):
                    selected[idx] = replacement
                    selected_symbols.add(replacement["sym"])
                    current_count += 1
                    break
            else:
                break
        return sorted(selected, key=lambda x: x["score"], reverse=True)

    @staticmethod
    @ttl_cache(maxsize=100, ttl=900)
    def _fetch_signals(symbol: str):
        for ticker_symbol in _ticker_candidates(symbol):
            try:
                df = yf.Ticker(ticker_symbol).history(period="1mo", interval="1d")
                df = df.dropna(subset=["Close"])
                if df.empty or len(df) < 14:
                    continue
                close = df["Close"]
                current = float(close.iloc[-1])
                window = min(20, len(close))
                ma20 = float(close.rolling(window).mean().iloc[-1])
                rsi_val = float(AdvisorService._rsi(close).iloc[-1])
                return {
                    "current_price": round(current, 2),
                    "rsi": 50.0 if np.isnan(rsi_val) else round(rsi_val, 2),
                    "trend": "BULLISH" if current > ma20 else "BEARISH",
                }
            except Exception:
                continue
        return None

    @staticmethod
    @ttl_cache(maxsize=100, ttl=1800)
    def _fetch_signals_and_sentiment(symbol: str):
        signals = AdvisorService._fetch_signals(symbol)
        if not signals:
            return None
            
        try:
            working_ticker = _working_ticker(symbol)
            stock_obj = yf.Ticker(working_ticker, session=_yf_session)
            news = getattr(stock_obj, 'news', []) or []
            sentiments = []
            for item in news[:5]:
                content = item.get("content") or {}
                title = item.get("title") or content.get("title") or ""
                summary = item.get("summary") or item.get("publisher") or content.get("summary") or content.get("description") or ""
                sentiments.append(AdvisorService._analyze_sentiment(f"{title} {summary}"))
            sentiment_score = np.mean(sentiments) if sentiments else 50.0
        except Exception:
            sentiment_score = 50.0
            
        return {
            "signals": signals,
            "sentiment_score": sentiment_score
        }

    @staticmethod
    def _score(signals: dict, sentiment_score: float, risk_level: str, duration: str, is_goal_match: bool) -> int:
        score = 0
        if is_goal_match: score += 40
        
        technical = 15 if signals["trend"] == "BULLISH" else 0
        rsi = signals["rsi"]
        if 35 <= rsi <= 55: technical += 10
        elif 20 <= rsi < 35: technical += 8
        elif 55 < rsi <= 65: technical += 6
        elif 65 < rsi <= 72: technical += 2
        score += technical
        
        score += (sentiment_score / 100) * 20
        score += 10 * DURATION_MULTIPLIERS.get(duration, {}).get(risk_level, 1.0)
        return int(min(100, max(0, score)))

    @staticmethod
    def _calculate_confidence(score: int, sentiment_score: float, rsi: float, trend: str) -> int:
        confidence = score
        if sentiment_score > 65: confidence = min(100, confidence + 8)
        elif sentiment_score < 35: confidence = min(100, confidence + 5)
        if 30 < rsi < 70: confidence = min(100, confidence + 5)
        return int(max(30, min(100, confidence)))

    @staticmethod
    def _reason(meta: dict, signals: dict, goal: str, duration: str, sentiment_score: float) -> str:
        name = meta.get("name", "This stock")
        sector = meta.get("sector", "the market")
        desc = meta.get("desc", "")
        risk = meta.get("risk", "medium")
        dur = DURATION_LABELS.get(duration, "the long term")

        context = desc if desc else f"{name} is a key player in the {sector} sector."
        
        if goal == "wealth":
            alignment = f"As a higher-risk play, it's an aggressive wealth creation candidate over the next {dur}." if risk == "high" else f"It offers steady, compounding wealth creation potential over the next {dur}."
        elif goal == "income":
            alignment = f"Its stable business model makes it a solid choice for consistent returns."
        elif goal == "retirement":
            alignment = f"Given its profile, it serves as a reliable anchor for a long-term retirement portfolio."
        elif goal == "education":
            alignment = f"It balances necessary growth with reasonable safety to help fund education goals over {dur}."
        elif goal == "safety":
            alignment = f"This is a defensive, capital-preservation pick designed to weather market volatility."
        else:
            alignment = f"It aligns well with your {goal} strategy over {dur}."

        rsi = signals["rsi"]
        trend = signals["trend"]
        
        if trend == "BULLISH":
            tech = "The stock is currently riding a strong upward trend."
            if rsi < 40: tech += " Surprisingly, it is not overbought yet, presenting a very attractive entry point."
            elif rsi <= 60: tech += " Momentum is healthy with room left to run."
            else: tech += " It has rallied hard recently, so consider accumulating on small dips."
        else:
            tech = "The stock is currently consolidating or in a downtrend."
            if rsi < 35: tech += " It appears technically oversold, which often signals a value-buying opportunity."
            else: tech += " It's building a base; patience may be rewarded once the trend shifts."

        sentiment = "Recent news is optimistic, providing strong tailwinds." if sentiment_score >= 65 else "Media coverage has been generally positive." if sentiment_score > 55 else "Current news sentiment is cautious, so keep an eye on developments." if sentiment_score < 40 else ""
        return f"{context} {alignment} {tech} {sentiment}".strip()

    @staticmethod
    def get_recommendations(goal: str, duration: str, risk: str, budget: float, investment_type: str = "one-time", investment_months: Optional[int] = None) -> list[dict]:
        is_sip = investment_type in {"monthly", "sip"}
        months = int(investment_months or DEFAULT_MONTHS_BY_DURATION.get(duration, 36))
        months = max(1, months)
        total_budget = budget * months if is_sip else budget
        target_count = TARGET_STOCKS_BY_DURATION.get(duration, 6)

        key = f"advisor:{goal}:{duration}:{risk}:{investment_type}:{months}:{int(total_budget//10000)}"
        
        cached_value = redis_client.get(key)
        if cached_value:
            return json.loads(cached_value)

        candidates = AdvisorService._advisor_candidates(goal, risk)

        results_map = {}
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(AdvisorService._fetch_signals_and_sentiment, sym): sym for sym in candidates}
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    result = future.result()
                    if result:
                        results_map[sym] = result
                except Exception:
                    pass

        scored = []
        for sym, data in results_map.items():
            meta = UNIVERSE.get(sym, {})
            signals = data["signals"]
            sentiment_score = data["sentiment_score"]
            
            stock_risk = meta.get("risk", "medium")
            is_goal_match = sym in GOAL_CANDIDATES.get(goal, [])
            score = AdvisorService._score(signals, sentiment_score, stock_risk, duration, is_goal_match)
            score = int(min(100, max(0, score + AdvisorService._opportunistic_bonus(meta, goal, duration, risk))))
            confidence = AdvisorService._calculate_confidence(score, sentiment_score, signals["rsi"], signals["trend"])
            scored.append({
                "sym": sym,
                "meta": meta,
                "signals": signals,
                "sentiment_score": sentiment_score,
                "score": score,
                "confidence": confidence,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        selected = AdvisorService._select_recommendations(scored, goal, duration, risk, target_count)

        if not selected:
            return []

        per_stock = round(total_budget / len(selected), 0)
        monthly_per_stock = round(budget / len(selected), 0) if is_sip else None

        results = []
        for item in selected:
            sym     = item["sym"]
            meta    = item["meta"]
            signals = item["signals"]
            sentiment_score = item["sentiment_score"]
            confidence = item["confidence"]
            price   = signals["current_price"]
            shares  = int(per_stock / price) if price > 0 else 0

            results.append({
                "symbol":               sym.replace(".NS", "").replace(".BO", ""),
                "name":                 meta.get("name", sym),
                "sector":               meta.get("sector", ""),
                "description":          meta.get("desc", ""),
                "risk_level":           meta.get("risk", "medium"),
                "cap_segment":          meta.get("cap", "large"),
                "current_price":        price,
                "trend":                signals["trend"],
                "rsi":                  signals["rsi"],
                "sentiment_score":      round(sentiment_score, 1),
                "confidence":           confidence,
                "reason":               AdvisorService._reason(meta, signals, goal, duration, sentiment_score),
                "suggested_allocation": per_stock,
                "monthly_allocation":    monthly_per_stock,
                "investment_type":       "monthly" if is_sip else "one-time",
                "investment_months":     months if is_sip else None,
                "total_investment":      total_budget,
                "shares_you_can_buy":   shares,
            })

        try:
            redis_client.set(key, json.dumps(results), ex=900)
        except Exception:
            pass
            
        return results
