from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from database import init_db
import os
from routers import products, auth

# Инициализация приложения
app = FastAPI()

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
