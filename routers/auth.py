from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
import schemas, models, auth
from slowapi import Limiter
from database import get_db
import os
from auth import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

limiter = Limiter(key_func=lambda: "global")

IS_PROD = os.getenv("ENV") == "production"

@limiter.limit("3 per hour")
@router.post("/register")
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
@router.post("/login", response_model=schemas.TokenResponse)
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
@router.post("/refresh", response_model=schemas.TokenResponse)
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
@router.post("/logout")
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
@router.get("/me", response_model=schemas.UserResponse)
def get_current_user_info(request: Request, user=Depends(auth.get_current_user)):
  return {"email": user.email, "name": user.name, "is_admin": user.is_admin}