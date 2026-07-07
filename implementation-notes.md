# Implementation Notes

Living log of decisions, deviations, and open questions for the phase-gated
predictor-verification work. Newest phase on top.

---

## Phase 2 — Realistic Backtesting Engine

### Decisions
- **Data source = yfinance now, behind a swappable `DataSource` interface**
  (`backtest/data_source.py`). A better vendor (NSE Bhavcopy, broker API,
  purchased dataset) can be dropped in later without touching the engine.
  Daily OHLCV, ~5y, on-disk cached. (User chose "Both (yfinance now, adapter
  later)".)
- **What is backtested = the *technical* consensus only.** `predict_stock`
  pulls live NLP sentiment and live fundamentals, and we have **no point-in-time
  archive** of either — applying today's values to a past bar would be
  lookahead. So the historical replay holds sentiment and fundamentals
  **NEUTRAL** (their votes contribute 0). Stated as a limitation.
- **Lookahead safety.** Every indicator used (RSI/MACD/EMA/Bollinger/Stoch/ADX)
  is causal, so computing over the full series and reading at day *t* equals
  computing on the series truncated at *t*. A test asserts this equality; a
  second test asserts every trade's entry date is strictly after its signal
  date. Signals act at **next-day open**, never the signal-day price.
- **Walk-forward only.** Expanding-window folds (mirrors `train_ranker`); the
  single tunable knob (min-confidence threshold, grid 50/60/70/80) is calibrated
  on each train window and applied to the strictly-later test window. Only
  out-of-sample trades feed the reported metrics — no in-sample numbers in the
  API or UI.
- **Cost model** (`backtest/cost_model.py`): brokerage (capped), STT, exchange
  txn, SEBI, GST, stamp duty, and slippage — each a configurable rate with
  conservative NSE-delivery defaults (slippage 10 bps/side). `trade_pnl` is
  direction-aware and unit-tested against hand-computed values.
- **Trade model:** long on BULLISH / short on BEARISH / skip NEUTRAL; one
  position per symbol at a time; hold `holding_days` trading days; exit at close.
  Position sizing is a simple fixed fraction of equity — **real risk sizing is
  Phase 4's job**.

### Deviations
- The existing `BacktestingService` (naive per-symbol MA/RSI, no costs, no
  walk-forward) is **left intact** at `/market/backtest/{symbol}`; Phase 2 is a
  new engine under `/backtest/*`. Not reused.

### Open Questions / Known limitations
- **Sharpe/Sortino are trade-return based** (annualised by trades/year), not a
  daily mark-to-market curve — surfaced in `risk_note`. A daily-MTM portfolio
  simulator (needed for a fully standard Sharpe and for overlapping-position
  accounting) is deferred; flag if you want it before Phase 3.
- **Shorts are modelled with the delivery cost structure** symmetrically
  (conservative). True Indian intraday/SLB short costs differ.
- **Sentiment/fundamentals excluded** means the backtest tests a *subset* of the
  live consensus. The live edge (Phase 1 ledger) includes those inputs, so
  Phase 1 and Phase 2 are measuring related-but-not-identical models. Worth
  keeping in mind when comparing.
- Backtest currently caps the universe at 40 symbols per run for runtime.

### Files touched
- `backend/app/services/ai/backtest/` — **new package**: `cost_model.py`,
  `data_source.py`, `historical_consensus.py`, `walkforward_backtest.py`.
- `backend/app/api/v1/endpoints/backtest.py` — new (`POST /backtest/run`,
  `GET /backtest/config`); registered in `router.py`.
- `frontend/pages/backtest.js` — new config panel + equity/drawdown charts +
  metrics + per-regime table.
- `frontend/components/Navbar.js` — Backtest nav link + icon.
- `backend/tests/test_backtest.py` — new (cost math, lookahead guard, metrics,
  trade P&L, end-to-end on synthetic data).

---

## Phase 1 — Signal Ledger

### Decisions
- **Signal source = the consensus predictor (`predict_stock`), not the ranker.**
  Phase 1's required fields (direction, regime, per-indicator states, NLP
  sentiment) exist only on the consensus predictor. A new scheduled job scans a
  fixed watchlist and appends one immutable signal per symbol. (User deferred
  the choice; recommended and adopted.)
- **Scope = focused watchlist, 3 scans/session.** ~30 liquid large-cap NSE names
  (`SIGNAL_UNIVERSE` in `signal_ledger_service.py`), scanned at 09:20 / 12:00 /
  15:15 IST (Mon–Fri). Chosen because `predict_stock` is heavy and the shared
  yfinance session is not thread-safe, so symbols score roughly sequentially.
  The watchlist is a plain editable constant.
- **Horizons = 1h / 1d / 3d, all honored.** 1d/3d scored from daily bars (same
  pattern as `evaluate_pick_outcomes`); 1h scored from yfinance 60-minute
  intraday bars. This uses the *same* data vendor already in the repo, so it
  does not require a new ingestion source.
- **Append-only enforced structurally.** `signal_ledger` is insert-only;
  realized outcomes live in a separate `signal_outcomes` table written once per
  `(signal_id, horizon)`. The repository exposes no update/delete methods and
  the API exposes no signal-mutating routes. Corrections = a new ledger row with
  `corrects_signal_id` referencing the original.
- **Direction-aware P&L.** A short signal is a win when price falls;
  `compute_return` inverts short returns and `is_hit` uses the position-signed
  return. Neutral signals record a raw informational return and are excluded
  from hit-rate (`hit = NULL`). Covered by `tests/test_signal_ledger.py`.
- **Timestamps stored as ISO-8601 UTC strings with offset** (e.g.
  `2026-07-06T09:20:00+00:00`) — portable across Postgres and the SQLite
  fallback, lexically sortable, unambiguous about timezone.
- **Regime label** derived from the ADX threshold the consensus weighting
  already uses: `trending` if ADX > 25 else `range_bound`.

### Deviations
- **`predict_stock` return was extended additively** with `regime`,
  `indicator_states`, `adx`, and `model_version`. No existing keys changed;
  the frontend ignores unknown keys. Needed so the ledger logs the model's
  actual indicator states rather than recomputing them (avoids drift).
- **Timezone-aware UTC** is used for new timestamps, versus the existing naive
  `datetime.now()` used elsewhere (daily picks). Deliberate, per the project
  rule to store UTC with tz info.
- **Scan is not auto-triggered on startup** (unlike daily picks) to avoid
  spamming the ledger on every dev restart. Signals come only from the
  scheduled jobs or the admin `POST /ledger/scan` trigger.

### Open Questions
- **NSE holiday calendar is not handled.** `generate_signals` skips weekends
  only. On an NSE holiday the scan will run and log signals against stale prices
  (the last close). Options: add a holiday list, or filter out signals whose
  entry price didn't change. Needs a decision before the "full session" gate is
  claimed on a holiday week.
- **Exact watchlist membership** — seeded with 30 large caps; confirm or edit.
- **1h honesty on gap opens / illiquid bars** — 60m intraday from yfinance can
  be sparse; such signals are left unscored rather than approximated. Acceptable
  for Phase 1, revisit if 1h coverage is thin.
- **Auth on Track Record** — read endpoints require any logged-in user;
  `POST /ledger/scan` uses the existing `X-Admin-Token`. Confirm this is the
  intended visibility (Daily Edge, by contrast, is public).

### Files touched
- `backend/app/services/ai/prediction_service.py` — additive fields + `MODEL_VERSION`.
- `backend/app/repositories/signal_repository.py` — new (schema, insert, write-once outcome, reads).
- `backend/app/services/ai/signal_ledger_service.py` — new (scan, scoring, pure P&L helpers, aggregation).
- `backend/app/api/v1/endpoints/ledger.py` — new (signals / stats / coverage / export.csv / admin scan).
- `backend/app/api/v1/router.py` — register ledger router.
- `backend/app/main.py` — table init + 4 scheduler jobs (3 scans + scoring).
- `frontend/pages/track-record.js` — new Track Record page.
- `frontend/components/Navbar.js` — nav link + icon.
- `backend/tests/test_signal_ledger.py` — new tests.
