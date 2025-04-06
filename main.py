from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import init_db
import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from routers import products, auth

app = FastAPI()

@app.on_event("startup")
def startup_event():
    init_db()

IS_PROD = os.getenv("ENV") == "production"

limiter = Limiter(key_func=get_remote_address)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Разрешаем запросы с фронтенда (Nuxt 3)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем router для продуктов
app.include_router(products.router, prefix="/api")
# Подключаем router для аутентификации
app.include_router(auth.router, prefix="/api")

@app.get("/ping_db")
def ping_db():
    return {"message": "Database connection successful!"}
