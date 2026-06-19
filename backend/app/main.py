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
    
    try:
        logger.info("Initializing database schemas...")
        UserRepository.init_users_db()
        PicksRepository.init_daily_picks_db()
        PortfolioRepository.init_portfolio_db()
        WatchlistRepository.init_watchlist_db()
        AlertRepository.init_alert_db()
        logger.info("Database schemas initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        
    # 2. Pre-load XGBoost models asynchronously
    from app.services.ai.model_loader import load_all_models_async
    load_all_models_async()

    # 3. Setup Scheduler Job for daily recommendations and price alerts
    from app.services.market.market_service import MarketService
    from app.services.market.alert_service import AlertService
    scheduler.add_job(MarketService.generate_daily_picks, 'cron', hour=0, minute=0)
    scheduler.add_job(AlertService.check_alerts, 'interval', minutes=1)
    scheduler.start()
    
    # 4. Trigger initial picks calculation in the background (skip on Render to save memory on startup)
    if not os.environ.get("RENDER"):
        thread = threading.Thread(target=MarketService.generate_daily_picks, kwargs={"force": True})
        thread.daemon = True
        thread.start()
    else:
        logger.info("Skipping initial picks calculation on Render startup to prevent memory spikes.")
    yield
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



