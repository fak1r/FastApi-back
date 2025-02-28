from pydantic import BaseModel, EmailStr

class UserResponse(BaseModel):
  email: EmailStr
  name: str

# Запрос на логин
class LoginRequest(BaseModel):
  email: EmailStr
  password: str

# Ответ при успешном логине
class TokenResponse(BaseModel):
  access_token: str
  token_type: str = "bearer"
  user: UserResponse

class RegisterRequest(BaseModel):
  name: str
  email: EmailStr  
  password: str