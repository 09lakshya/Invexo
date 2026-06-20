from fastapi import APIRouter, Query
from typing import List
import json
import os

router = APIRouter(prefix="/search", tags=["Search"])

# Load STOCKS from the database/services directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
stocks_file = os.path.join(BASE_DIR, "services", "stocks.json")

try:
    with open(stocks_file, "r", encoding="utf-8") as f:
        STOCKS = json.load(f)
except Exception as e:
    import logging
    logging.error(f"Search endpoint: failed to load stocks.json from {stocks_file}: {e}")
    STOCKS = []

SYMBOL_ALIASES = [
    {"symbol": "TATAMOTORS", "name": "Tata Motors Limited"},
]
existing_symbols = {s["symbol"] for s in STOCKS}
for alias in SYMBOL_ALIASES:
    if alias["symbol"] not in existing_symbols:
        STOCKS.append(alias)

TRENDING = ["RELIANCE", "TCS", "INFY", "HDFCBANK"]

@router.get("")
def search(q: str = Query("")):
    if not q:
        # Get names for trending symbols
        trending_stocks = []
        for sym in TRENDING:
            matched = [s for s in STOCKS if s["symbol"].lower() == sym.lower()]
            name = matched[0]["name"] if matched else sym
            trending_stocks.append({"symbol": sym, "name": name})
        return trending_stocks

    q_lower = q.lower().strip()
    tokens = q_lower.split()
    if not tokens:
        return []

    results = []
    for stock in STOCKS:
        score = 0
        symbol_lower = stock["symbol"].lower()
        name_lower = stock["name"].lower()
        name_words = name_lower.split()

        # 1. Exact matches
        if symbol_lower == q_lower:
            score += 100
        elif name_lower == q_lower:
            score += 80

        # 2. Substring matches on the full query
        elif symbol_lower.startswith(q_lower):
            score += 50
        elif q_lower in symbol_lower:
            score += 30

        if q_lower in name_lower:
            score += 20
            # Check if it starts a word boundary in the name
            if name_lower.startswith(q_lower) or f" {q_lower}" in name_lower:
                score += 15

        # 3. Individual token matches
        matched_tokens_count = 0
        for token in tokens:
            token_score = 0
            if symbol_lower == token:
                token_score += 15
            elif symbol_lower.startswith(token):
                token_score += 8
            elif token in symbol_lower:
                token_score += 4

            # Check if token matches start of any word in the stock name
            word_start_match = any(word.startswith(token) for word in name_words)
            if word_start_match:
                token_score += 5
            elif token in name_lower:
                token_score += 2

            if token_score > 0:
                score += token_score
                matched_tokens_count += 1

        # Heavily penalize or exclude results that do not match all search tokens
        if matched_tokens_count == len(tokens):
            score += 25
        elif matched_tokens_count > 0:
            # Partial matches: penalize by scaling down the score
            score = score * (matched_tokens_count / len(tokens)) * 0.4
        else:
            score = 0

        if score > 0:
            results.append({**stock, "score": score})

    results.sort(key=lambda x: x["score"], reverse=True)
    return [{"symbol": r["symbol"], "name": r["name"]} for r in results[:10]]
