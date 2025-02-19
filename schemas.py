from pydantic import BaseModel, EmailStr

# Модель для входящих данных (логин)
class LoginRequest(BaseModel):
  email: EmailStr
  password: str

# Модель для ответа при успешном логине
class TokenResponse(BaseModel):
  access_token: str
  refresh_token: str
  token_type: str = "bearer"

class RegisterRequest(BaseModel):
  name: str
  email: EmailStr  
  password: str