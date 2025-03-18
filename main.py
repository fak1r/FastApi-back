from fastapi import FastAPI, Depends, HTTPException, Form, Response, Request, Query
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from database import SessionLocal, init_db
import schemas, models, auth, os
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import List, Optional
from routers import products

app = FastAPI()

init_db()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

IS_PROD = os.getenv("ENV") == "production"

limiter = Limiter(key_func=get_remote_address)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS").split(",")

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
app.include_router(products.router)

def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()

@app.get("/ping_db")
def ping_db(db: Session = Depends(get_db)):
  return {"message": "Database connection successful!"}

@limiter.limit("3 per hour")
@app.post("/register")
def register(request: schemas.RegisterRequest, db: Session = Depends(get_db)):  # <-- Принимаем JSON-данные
  # Проверяем, есть ли уже такой email в БД
  existing_user = db.query(models.User).filter(models.User.email == request.email).first()
  if existing_user:
    raise HTTPException(status_code=400, detail="Email already registered")

  # Создаём нового пользователя
  hashed_password = auth.hash_password(request.password)
  new_user = models.User(name=request.name, email=request.email, hashed_password=hashed_password)

  db.add(new_user)
  db.commit()
  db.refresh(new_user)
  return {"message": "User registered successfully", "user": {"id": new_user.id, "email": new_user.email}}

@limiter.limit("5 per minute")
@app.post("/login", response_model=schemas.TokenResponse)
def login(request: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
  user = db.query(models.User).filter(models.User.email == request.email).first()
  if not user or not auth.verify_password(request.password, user.hashed_password):
    raise HTTPException(status_code=400, detail="Invalid email or password")

  access_token = auth.create_access_token({"sub": user.email})
  refresh_token = auth.create_refresh_token({"sub": user.email})

  user.refresh_token = refresh_token
  db.commit()

  # Устанавливаем refresh-токен в cookie
  response.set_cookie(
    key="refresh_token",
    value=refresh_token,
    httponly=True,
    samesite="Strict" if IS_PROD else "None",
    secure=True,
  )

  return {"access_token": access_token, "token_type": "bearer", "user": {"email": user.email, "name": user.name, "is_admin": user.is_admin }}

@limiter.limit("5 per minute")
@app.post("/refresh", response_model=schemas.TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
  # Берём refresh-токен из cookie
  refresh_token = request.cookies.get("refresh_token")
  if not refresh_token:
    raise HTTPException(status_code=401, detail="No refresh token in cookies")


  # Декодируем refresh-токен
  payload = auth.verify_token(refresh_token, auth.REFRESH_SECRET_KEY)
  if not payload:
    raise HTTPException(status_code=401, detail="Invalid refresh token")

  # Ищем пользователя в БД
  user = db.query(models.User).filter(models.User.email == payload["sub"]).first()
  if not user or user.refresh_token != refresh_token:
    if user:
      user.refresh_token = None
      db.commit()
    response.delete_cookie("refresh_token")
    raise HTTPException(status_code=401, detail="Invalid refresh token")

  # Создаём новые токены
  new_access_token = auth.create_access_token({"sub": payload["sub"]})
  new_refresh_token = auth.create_refresh_token({"sub": payload["sub"]})

  # Обновляем refresh_token в БД
  user.refresh_token = new_refresh_token
  db.commit()

  # Ставим новый refresh-токен в cookie
  response.set_cookie(
    key="refresh_token",
    value=new_refresh_token,
    httponly=True,  
    samesite="Strict" if IS_PROD else "None",
    secure=True,
  )

  return {"access_token": new_access_token, "user": {"email": user.email, "name": user.name, "is_admin": user.is_admin }}

@limiter.limit("5 per minute")
@app.post("/logout")
def logout(response: Response, db: Session = Depends(get_db), request: Request = None):
  refresh_token = request.cookies.get("refresh_token")

  if refresh_token:
    # Ищем пользователя в БД по refresh-токену
    user = db.query(models.User).filter(models.User.refresh_token == refresh_token).first()
    if user:
      # Удаляем refresh_token из БД
      user.refresh_token = None 
      db.commit()
  
  response.delete_cookie("refresh_token")

  return {"message": "Logged out"}

@limiter.limit("5 per minute")
@app.get("/me", response_model=schemas.UserResponse)
def get_current_user_info(request: Request, user=Depends(auth.get_current_user)):
  return {"email": user.email, "name": user.name, "is_admin": user.is_admin}