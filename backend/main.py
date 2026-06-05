from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

load_dotenv()

from routers import market, predict, search, news, portfolio, advisor, auth
from services.rate_limiter import rate_limit_auth

app = FastAPI()

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
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

default_origins = "https://invexo-one.vercel.app,http://localhost:3000,http://localhost:3001"
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
        allow_origin_regex=r"https://invexo-one(?:-[a-zA-Z0-9-]+)?\.vercel\.app",
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(market.router)
app.include_router(predict.router)
app.include_router(search.router)
app.include_router(news.router)          # ← added
app.include_router(portfolio.router)     # ← added
app.include_router(advisor.router)       # ← added
app.include_router(auth.router, dependencies=[Depends(rate_limit_auth)])

