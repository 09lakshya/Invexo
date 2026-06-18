from fastapi import APIRouter
from app.api.v1.endpoints import auth, market, portfolio, advisor, admin

api_router = APIRouter()

# Include version 1 routers
api_router.include_router(auth.router)
api_router.include_router(market.router)
api_router.include_router(portfolio.router)
api_router.include_router(advisor.router)
api_router.include_router(admin.router)
