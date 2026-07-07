from fastapi import APIRouter
from app.api.v1.endpoints import auth, market, portfolio, advisor, admin, search, news, predict, watchlist, alert, signal_alert, copilot, support, ledger, backtest

api_router = APIRouter()

# Include version 1 routers
api_router.include_router(auth.router)
api_router.include_router(market.router)
api_router.include_router(portfolio.router)
api_router.include_router(advisor.router)
api_router.include_router(admin.router)
api_router.include_router(search.router)
api_router.include_router(news.router)
api_router.include_router(predict.router)
api_router.include_router(watchlist.router)
api_router.include_router(alert.router)
api_router.include_router(signal_alert.router)
api_router.include_router(copilot.router)
api_router.include_router(support.router)
api_router.include_router(ledger.router)
api_router.include_router(backtest.router)

