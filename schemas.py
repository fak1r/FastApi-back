from pydantic import BaseModel, EmailStr, HttpUrl
from typing import List, Optional, Dict, TYPE_CHECKING

class UserResponse(BaseModel):
  email: EmailStr
  name: str
  is_admin: bool

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

### КАТЕГОРИЯ ###
class CategoryBase(BaseModel):
  name: str

class CategoryCreate(CategoryBase):
  pass

class CategoryResponse(CategoryBase):
  id: int
  producers: List["ProducerResponse"] = []

  class Config:
    from_attributes = True

### ПРОИЗВОДИТЕЛЬ ###
class ProducerBase(BaseModel):
  name: str
  category_id: int

class ProducerCreate(ProducerBase):
  pass

class ProducerResponse(ProducerBase):
  id: int
  product_lines: List["ProductLineResponse"] = []

  class Config:
    from_attributes = True

### ЛИНЕЙКА ТОВАРОВ ###
class ProductLineBase(BaseModel):
  name: str
  producer_id: int

class ProductLineCreate(ProductLineBase):
  pass

class ProductLineResponse(ProductLineBase):
  id: int
  products: List["ProductResponse"] = []

  class Config:
    from_attributes = True

### ПРОДУКТ ###
class ProductBase(BaseModel):
  name: str
  description: Optional[str] = None
  price: float
  product_line_id: int
  favorite: bool = False
  details: Optional[Dict[str, str]] = None  # JSONB-поле для специфических характеристик

class ProductCreate(ProductBase):
  pass

class ProductImageResponse(BaseModel):
  id: int
  image_url: str

  class Config:
    from_attributes = True

class ProductResponse(ProductBase):
  id: int
  images: List[ProductImageResponse] = []

  class Config:
    from_attributes = True

if TYPE_CHECKING:
  from schemas import ProductLineResponse, ProducerResponse, CategoryResponse