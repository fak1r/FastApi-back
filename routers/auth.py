from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from database import get_db
import os

import schemas, models, security
from security import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])
IS_PROD = os.getenv("ENV") == "production"

@router.post("/register")
def register(request: schemas.RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = security.hash_password(request.password)
    new_user = models.User(
        name=request.name,
        email=request.email,
        hashed_password=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "user": {"id": new_user.id, "email": new_user.email}
    }

@router.post("/login", response_model=schemas.TokenResponse)
def login(request: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.email).first()

    if not user or not security.verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    access_token = security.create_access_token({"sub": user.email})
    refresh_token = security.create_refresh_token({"sub": user.email})

    user.refresh_token = refresh_token
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="Strict" if IS_PROD else "None",
        secure=True,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"email": user.email, "name": user.name, "is_admin": user.is_admin}
    }

@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token in cookies")

    payload = security.verify_token(refresh_token, security.REFRESH_SECRET_KEY)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(models.User).filter(models.User.email == payload["sub"]).first()
    if not user or user.refresh_token != refresh_token:
        if user:
            user.refresh_token = None
            db.commit()
        response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access_token = security.create_access_token({"sub": payload["sub"]})
    new_refresh_token = security.create_refresh_token({"sub": payload["sub"]})

    user.refresh_token = new_refresh_token
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        samesite="Strict" if IS_PROD else "None",
        secure=True,
    )

    return {
        "access_token": new_access_token,
        "user": {"email": user.email, "name": user.name, "is_admin": user.is_admin}
    }

@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        user = db.query(models.User).filter(models.User.refresh_token == refresh_token).first()
        if user:
            user.refresh_token = None 
            db.commit()

    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}

@router.get("/me", response_model=schemas.UserResponse)
def get_current_user_info(user=Depends(get_current_user)):
    return {
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin
    }