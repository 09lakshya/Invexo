"""Broker statement parser.

Turns an uploaded holdings export (CSV / XLSX) from any of the supported
brokers into a normalized list of holdings the portfolio table understands:
``{symbol, company_name, quantity, buy_price}``.

Design notes
------------
* Brokers rename and reorder columns often, so detection is *fuzzy*: we match
  header cells against alias groups rather than hard-coding exact headers. The
  ``broker`` argument is a hint (mainly for which column holds the symbol and
  for nicer messaging), not a rigid schema.
* Zerodha / Angel One export a real ticker (e.g. ``INFY``). Groww / Upstox
  export a company *name* (e.g. ``Infosys Ltd``) plus an ISIN. For those we try
  to resolve the name against our known universe; whatever we cannot resolve is
  returned unresolved and the UI lets the user fix the symbol before committing.
"""

import csv
import io
import re

from app.services.market.advisor_service import UNIVERSE
from app.utils.logger import get_logger

logger = get_logger("statement_parser")

SUPPORTED_BROKERS = {"zerodha", "groww", "angelone", "upstox", "auto"}

# ── Header alias groups (normalized: lowercase, alnum + single spaces) ───────
_SYMBOL_ALIASES = [
    "symbol", "trading symbol", "tradingsymbol", "nse symbol", "bse symbol",
    "scrip", "scrip code", "scrip name", "ticker", "instrument",
]
_NAME_ALIASES = [
    "stock name", "company name", "company", "security name", "security",
    "name", "instrument name",
]
_QTY_ALIASES = [
    "quantity available", "quantity", "qty", "shares", "holding qty",
    "net qty", "closing qty", "free qty", "quantity long term", "qty.",
    "total qty", "cur. qty", "available qty",
]
_PRICE_ALIASES = [
    "average price", "avg price", "average buy price", "avg buy price",
    "avg cost", "average cost", "buy price", "buy avg", "buy average",
    "purchase price", "cost price", "avg. price", "avg. cost", "buy rate",
    "avg rate", "cost / share", "avg price / share", "buy avg.",
]

# Prefer these column *kinds* for the symbol, per broker.
_BROKER_SYMBOL_PREFERENCE = {
    "zerodha": ("symbol", "name"),
    "angelone": ("symbol", "name"),
    "groww": ("name", "symbol"),
    "upstox": ("name", "symbol"),
    "auto": ("symbol", "name"),
}


def _norm_header(s: str) -> str:
    """Normalize a header cell for alias matching."""
    s = re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())
    return re.sub(r"\s+", " ", s).strip()


def _norm_name(s: str) -> str:
    """Normalize a company name so 'Infosys Ltd.' == 'INFOSYS LIMITED'."""
    s = re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())
    for junk in (" limited", " ltd", " the ", " and ", " co "):
        s = s.replace(junk, " ")
    return re.sub(r"\s+", " ", s).strip()


# ── Known-symbol + name→symbol index built once from the curated universe ────
_KNOWN_SYMBOLS: set[str] = set()
_NAME_INDEX: dict[str, str] = {}
for _tk, _meta in UNIVERSE.items():
    _base = _tk.split(".")[0].upper()
    _KNOWN_SYMBOLS.add(_base)
    _nm = _meta.get("name") if isinstance(_meta, dict) else None
    if _nm:
        _NAME_INDEX[_norm_name(_nm)] = _base


def _match_alias(header: str, aliases: list[str]) -> int:
    """Return a match score for a header against an alias group (0 = no match).

    Exact alias match scores highest; a longer contained alias scores higher so
    'average price' beats a bare 'price' substring.
    """
    h = _norm_header(header)
    if not h:
        return 0
    best = 0
    for a in aliases:
        if h == a:
            best = max(best, 100 + len(a))
        elif a in h or h in a:
            best = max(best, 50 + len(a))
    return best


def _to_float(val) -> float | None:
    if val is None:
        return None
    s = re.sub(r"[^0-9.\-]", "", str(val))
    if s in ("", "-", ".", "-."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _load_rows(content: bytes, filename: str) -> list[list[str]]:
    """Load a CSV/XLSX file into a list of string rows (all cells as text)."""
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        try:
            import openpyxl  # optional dependency, only needed for Excel
        except ImportError:
            raise ValueError(
                "Excel parsing needs the 'openpyxl' package. Please export your "
                "holdings as CSV, or ask the admin to install openpyxl."
            )
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = []
        for r in ws.iter_rows(values_only=True):
            rows.append(["" if c is None else str(c) for c in r])
        wb.close()
        return rows

    # CSV / text: decode leniently and sniff the delimiter.
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    delim = ","
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        pass
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    return [list(r) for r in reader]


def _find_header_row(rows: list[list[str]]) -> int:
    """Broker CSVs often start with title/summary lines. Find the real header:
    the first row that matches at least a quantity/price alias plus a name/symbol.
    """
    for i, row in enumerate(rows[:40]):
        has_id = any(_match_alias(c, _SYMBOL_ALIASES) or _match_alias(c, _NAME_ALIASES) for c in row)
        has_num = any(_match_alias(c, _QTY_ALIASES) or _match_alias(c, _PRICE_ALIASES) for c in row)
        if has_id and has_num:
            return i
    return 0


def _pick_column(header: list[str], aliases: list[str]) -> int | None:
    best_idx, best_score = None, 0
    for idx, cell in enumerate(header):
        score = _match_alias(cell, aliases)
        if score > best_score:
            best_idx, best_score = idx, score
    return best_idx


def _resolve_symbol(raw_symbol: str, raw_name: str) -> tuple[str, str, bool]:
    """Return (symbol, company_name, recognized)."""
    symbol = ""
    if raw_symbol:
        symbol = re.sub(r"\.(ns|bo|nse|bse)$", "", raw_symbol.strip(), flags=re.I).upper()

    company = (raw_name or "").strip()

    # If we have no usable ticker, try matching the company name to the universe.
    if (not symbol or symbol not in _KNOWN_SYMBOLS) and company:
        matched = _NAME_INDEX.get(_norm_name(company))
        if matched:
            return matched, company or UNIVERSE.get(f"{matched}.NS", {}).get("name", company), True

    recognized = bool(symbol) and symbol in _KNOWN_SYMBOLS
    if recognized and not company:
        company = UNIVERSE.get(f"{symbol}.NS", {}).get("name", symbol)
    return symbol, company, recognized


def parse_statement(content: bytes, filename: str, broker: str) -> dict:
    """Parse an uploaded broker statement into normalized, reviewable rows."""
    broker = (broker or "auto").lower().strip()
    if broker not in SUPPORTED_BROKERS:
        broker = "auto"

    rows = _load_rows(content, filename)
    if not rows:
        raise ValueError("The file appears to be empty.")

    header_idx = _find_header_row(rows)
    header = rows[header_idx]

    sym_col = _pick_column(header, _SYMBOL_ALIASES)
    name_col = _pick_column(header, _NAME_ALIASES)
    qty_col = _pick_column(header, _QTY_ALIASES)
    price_col = _pick_column(header, _PRICE_ALIASES)

    # Broker hint: if it prefers name-as-symbol and both exist, that's fine —
    # _resolve_symbol already falls back to the name. We only need one of them.
    if sym_col is None and name_col is None:
        raise ValueError(
            "Couldn't find a stock/symbol column. Make sure you uploaded a "
            "holdings export (not an order/trade book)."
        )
    if qty_col is None:
        raise ValueError("Couldn't find a quantity column in the file.")

    prefer = _BROKER_SYMBOL_PREFERENCE.get(broker, ("symbol", "name"))

    parsed, warnings = [], []
    skipped = 0
    for row in rows[header_idx + 1:]:
        if not any(str(c).strip() for c in row):
            continue

        def cell(idx):
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        raw_symbol = cell(sym_col)
        raw_name = cell(name_col)
        # Honor the broker's preferred source when both look like identifiers.
        if prefer[0] == "name" and raw_name:
            raw_symbol, raw_name = "", raw_name or raw_symbol

        qty = _to_float(cell(qty_col))
        price = _to_float(cell(price_col)) if price_col is not None else None

        if not (raw_symbol or raw_name):
            continue
        if qty is None or qty <= 0:
            skipped += 1
            continue

        symbol, company, recognized = _resolve_symbol(raw_symbol, raw_name)

        row_warn = None
        if not symbol:
            row_warn = "Couldn't match to a ticker — set the symbol before importing."
        elif not recognized:
            row_warn = "Symbol not in our coverage list — double-check it."
        if price is None or price <= 0:
            price = 0.0
            row_warn = (row_warn + " " if row_warn else "") + "No buy price found — enter it manually."

        parsed.append({
            "symbol": symbol,
            "company_name": company or symbol,
            "quantity": round(qty, 4),
            "buy_price": round(price, 2),
            "recognized": recognized,
            "warning": row_warn,
        })

    if not parsed:
        raise ValueError(
            "No holdings could be read from the file. Check that it's a holdings "
            "export with quantity and average-price columns."
        )

    if skipped:
        warnings.append(f"Skipped {skipped} row(s) with zero or missing quantity.")

    unresolved = sum(1 for p in parsed if not p["symbol"] or not p["recognized"])
    if unresolved:
        warnings.append(
            f"{unresolved} of {len(parsed)} holdings need a quick review before importing."
        )

    return {
        "broker": broker,
        "count": len(parsed),
        "rows": parsed,
        "warnings": warnings,
    }
