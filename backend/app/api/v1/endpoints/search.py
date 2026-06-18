from fastapi import APIRouter, Query
from typing import List
import json
import os

router = APIRouter(prefix="/search", tags=["Search"])

# Load STOCKS from the database/services directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
stocks_file = os.path.join(BASE_DIR, "services", "stocks.json")

try:
    with open(stocks_file, "r", encoding="utf-8") as f:
        STOCKS = json.load(f)
except Exception:
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
        return [s["symbol"] for s in STOCKS if s["symbol"] in TRENDING]

    q_lower = q.lower().strip()
    results = []
    for stock in STOCKS:
        score = 0
        symbol = stock["symbol"].lower()
        name = stock["name"].lower()

        if symbol.startswith(q_lower):
            score += 5
        elif q_lower in symbol:
            score += 3

        if q_lower in name:
            score += 2

        if score > 0:
            results.append({**stock, "score": score})

    results.sort(key=lambda x: x["score"], reverse=True)
    return [r["symbol"] for r in results[:10]]
