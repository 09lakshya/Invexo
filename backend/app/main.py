from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
import os
import traceback
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager

from app.core.config import ENV, RENDER
from app.core.limiter import limiter
from app.api.v1.router import api_router
from app.utils.logger import get_logger

logger = get_logger("main")
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Database table migrations / initializations
    from app.repositories.user_repository import UserRepository
    from app.repositories.picks_repository import PicksRepository
    from app.repositories.portfolio_repository import PortfolioRepository
    from app.repositories.watchlist_repository import WatchlistRepository
    from app.repositories.alert_repository import AlertRepository
    from app.repositories.signal_alert_repository import SignalAlertRepository
    from app.repositories.support_repository import SupportRepository
    from app.repositories.signal_repository import SignalRepository

    try:
        logger.info("Initializing database schemas...")
        UserRepository.init_users_db()
        PicksRepository.init_daily_picks_db()
        PortfolioRepository.init_portfolio_db()
        WatchlistRepository.init_watchlist_db()
        AlertRepository.init_alert_db()
        SignalAlertRepository.init_signal_alert_db()
        SupportRepository.init_support_db()
        SignalRepository.init_signal_ledger_db()
        logger.info("Database schemas initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        
    # 2. Pre-load XGBoost models asynchronously
    from app.services.ai.model_loader import load_all_models_async
    load_all_models_async()

    # 3. Setup Scheduler Job for daily recommendations and price alerts.
    #
    # Only ONE process should own the scheduler. With multiple uvicorn workers
    # each would otherwise fire the same jobs — duplicate daily picks and, worse,
    # a duplicate alert email every single minute. We elect a single "leader"
    # via a short-lived Redis lock that the leader keeps renewing. If Redis is
    # unavailable (single-process/dev), we just run the scheduler locally.
    from app.services.market.market_service import MarketService
    from app.services.market.alert_service import AlertService
    from app.services.market.signal_alert_service import SignalAlertService
    from app.services.ai.signal_ledger_service import SignalLedgerService
    from app.core.redis import redis_client

    _SCHED_LOCK_KEY = "lock:scheduler_leader"
    _SCHED_LOCK_TTL = 120  # seconds

    def _try_become_scheduler_leader() -> bool:
        if not (redis_client.enabled and redis_client.client):
            # No shared coordinator available — assume single process.
            return True
        try:
            return bool(redis_client.client.set(_SCHED_LOCK_KEY, "leader", ex=_SCHED_LOCK_TTL, nx=True))
        except Exception as e:
            logger.error(f"Scheduler leader election failed, running locally: {e}")
            return True

    def _renew_scheduler_leadership():
        # Keep the lock warm so it never expires while this process is alive.
        if redis_client.enabled and redis_client.client:
            try:
                redis_client.client.set(_SCHED_LOCK_KEY, "leader", ex=_SCHED_LOCK_TTL)
            except Exception as e:
                logger.error(f"Failed to renew scheduler leadership lock: {e}")

    if _try_become_scheduler_leader():
        logger.info("This process is the scheduler leader; registering jobs.")
        scheduler.add_job(MarketService.generate_daily_picks, 'cron', hour=0, minute=0)
        scheduler.add_job(AlertService.check_alerts, 'interval', minutes=1)
        # Evaluate realized outcomes of past Daily Edge picks after NSE close
        # (12:00 UTC = 17:30 IST) so the page can show measured accuracy.
        scheduler.add_job(MarketService.evaluate_pick_outcomes, 'cron', hour=12, minute=0)
        # ── Signal Ledger (Phase 1) ──────────────────────────────────
        # Scan the consensus predictor across the watchlist three times per
        # session and score realized outcomes. Cron hours are UTC (server tz),
        # matching the evaluate_pick_outcomes convention above:
        #   03:50 UTC = 09:20 IST (post-open), 06:30 UTC = 12:00 IST (midday),
        #   09:45 UTC = 15:15 IST (pre-close). Mon–Fri only.
        scheduler.add_job(SignalLedgerService.generate_signals, 'cron',
                          day_of_week='mon-fri', hour=3, minute=50)
        scheduler.add_job(SignalLedgerService.generate_signals, 'cron',
                          day_of_week='mon-fri', hour=6, minute=30)
        scheduler.add_job(SignalLedgerService.generate_signals, 'cron',
                          day_of_week='mon-fri', hour=9, minute=45)
        # Fill 1h/1d/3d outcomes as horizons elapse (frequent enough for 1h).
        scheduler.add_job(SignalLedgerService.score_pending_outcomes, 'interval', minutes=30)
        # ── Buy/Sell signal alerts ───────────────────────────────────
        # Scan users' subscriptions + watchlists + holdings and notify on
        # actionable trend flips. Run a few minutes after each signal-ledger
        # scan so the consensus caches are warm. Cron hours are UTC:
        #   04:00 = 09:30 IST, 06:40 = 12:10 IST, 09:55 = 15:25 IST. Mon–Fri.
        scheduler.add_job(SignalAlertService.scan_and_notify, 'cron',
                          day_of_week='mon-fri', hour=4, minute=0)
        scheduler.add_job(SignalAlertService.scan_and_notify, 'cron',
                          day_of_week='mon-fri', hour=6, minute=40)
        scheduler.add_job(SignalAlertService.scan_and_notify, 'cron',
                          day_of_week='mon-fri', hour=9, minute=55)
        # Renew the leadership lock well before its TTL expires.
        scheduler.add_job(_renew_scheduler_leadership, 'interval', seconds=_SCHED_LOCK_TTL // 3)
        scheduler.start()
    else:
        logger.info("Another process holds the scheduler lock; skipping job registration.")
    
    # 4. Trigger initial picks calculation in the background. The ranker
    # path is light (one batched download + two small models, ~15s), so
    # this is safe on Render too — the old per-symbol scan wasn't.
    # Non-force: the daily lock file prevents duplicate work across workers,
    # and existing valid picks for today are kept.
    thread = threading.Thread(target=MarketService.generate_daily_picks)
    thread.daemon = True
    thread.start()

    # 5. Refresh market data cache with fresh prices on startup
    from app.api.v1.endpoints.market import refresh_market_cache
    cache_thread = threading.Thread(target=refresh_market_cache)
    cache_thread.daemon = True
    cache_thread.start()

    yield
    # Only the leader ever started the scheduler; shutting down a scheduler that
    # was never started raises SchedulerNotRunningError.
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(
    title="Invexo API",
    description="Production-grade real-time AI financial intelligence backend",
    version="1.0.0",
    lifespan=lifespan
)

# Register SlowAPI rate limiting handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── GLOBAL CATCH-ALL EXCEPTION HANDLER ──────
# Ensures unhandled exceptions return a proper JSON response
# that goes through the CORS middleware (instead of a raw 500
# that bypasses middleware and has no CORS headers).
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."}
    )

# ── SECURITY HEADERS MIDDLEWARE ──────
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    
    # Custom Permissions Policy
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # Content-Security-Policy (strictly block external assets, relax for docs)
    path = request.url.path
    if path in ["/docs", "/redoc", "/openapi.json"]:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
        
    return response

# CORS Configuration
default_origins = "https://invexo-one.vercel.app,https://invexo.co.in,https://www.invexo.co.in,http://localhost:3000,http://localhost:3001"
raw_origins = os.getenv("CORS_ORIGINS", "")
if raw_origins:
    allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
else:
    allowed_origins = [origin.strip() for origin in default_origins.split(",") if origin.strip()]

if "*" in allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=r"https://(?:[a-zA-Z0-9-]+\.)?(?:invexo-one\.vercel\.app|invexo\.co\.in)",
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include versioned API routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router) # Backwards-compatible root mount

@app.get("/")
def read_root():
    return {"message": "Invexo API is running", "env": ENV}

@app.get("/health")
def health_check():
    return {"status": "healthy"}



