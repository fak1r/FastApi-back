import os

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis

from database import init_db
from routers import products, auth

ENABLE_RATE_LIMITER = os.getenv("ENABLE_RATE_LIMITER", "false").lower() == "true"

if ENABLE_RATE_LIMITER:
    app = FastAPI(dependencies=[Depends(RateLimiter(times=3, seconds=60))])
else:
    app = FastAPI()

@app.on_event("startup")
async def startup():
    if ENABLE_RATE_LIMITER:
        redis_client = redis.from_url("redis://localhost", encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_client)

# Подключение к базе при запуске
@app.on_event("startup")
def startup_event():
    init_db()

# Прод/дев переменные
IS_PROD = os.getenv("ENV") == "production"
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# Раздача статики
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS для Nuxt 3
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутов
app.include_router(products.router, prefix="/api")
app.include_router(auth.router, prefix="/api")

# Пинг для проверки БД
@app.get("/ping_db")
def ping_db():
    return {"message": "Database connection successful!"}
