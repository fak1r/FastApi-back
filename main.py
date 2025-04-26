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
import logging

ENV = os.getenv('ENV', 'development')

ENABLE_RATE_LIMITER = os.getenv("ENABLE_RATE_LIMITER", "false").lower() == "true"
SHOW_DOCS = os.getenv("SHOW_DOCS", "true").lower() == "true"

# Настройки документации
docs_kwargs = {}
if not SHOW_DOCS:
    docs_kwargs = {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None
    }

if ENABLE_RATE_LIMITER:
    app = FastAPI(
        dependencies=[Depends(RateLimiter(times=30, seconds=60))],
        **docs_kwargs
    )
else:
    app = FastAPI(**docs_kwargs)

@app.on_event("startup")
async def startup():
    if ENABLE_RATE_LIMITER:
        redis_client = redis.from_url("redis://redis:6379", encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_client)

# Подключение к базе при запуске
@app.on_event("startup")
def startup_event():
    init_db()

ALLOWED_ORIGINS = list(set(os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")))

# Раздача статики
if ENV == 'production':
    static_path = '/var/www/static'
else:
    static_path = os.path.join(os.path.dirname(__file__), 'static')

app.mount("/static", StaticFiles(directory=static_path), name="static")

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

# Логгирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"✅ Limiter = {ENABLE_RATE_LIMITER}")
logger.info(f"✅ Docs = {SHOW_DOCS}")