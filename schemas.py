from pydantic import BaseModel, EmailStr, HttpUrl
from typing import List, Optional, Dict, TYPE_CHECKING, Literal

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
    slug: str

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int

    class Config:
        from_attributes = True

### ПРОИЗВОДИТЕЛЬ ###
class ProducerBase(BaseModel):
    name: str
    category_id: int
    slug: str

class ProducerCreate(ProducerBase):
    pass

class ProducerResponse(ProducerBase):
    id: int

    class Config:
        from_attributes = True

### ЛИНЕЙКА ТОВАРОВ ###
class ProductLineBase(BaseModel):
    name: str
    producer_id: int
    slug: str

class ProductLineCreate(ProductLineBase):
    pass

class ProductLineResponse(ProductLineBase):
    id: int

    class Config:
        from_attributes = True

### ПРОДУКТ ###
class ProductBase(BaseModel):
    name: str
    slug: str
    price: float
    product_line_id: int
    favorite: bool = False
    details: Optional[Dict[str, str]] = None  # JSONB-поле для специфических характеристик
    img_mini: Optional[List[str]] = None

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
    self: Optional[str] = None
    full_name: Optional[str] = None 

    class Config:
        from_attributes = True

class ProductPreview(BaseModel):
    id: int
    name: str
    slug: str 
    price: float
    favorite: bool
    product_line_id: int
    img_mini: Optional[List[str]] = None
    self: Optional[str] = None

    class Config:
        from_attributes = True

class PaginatedProducts(BaseModel):
    items: List[ProductPreview]
    total: int
    page: int
    limit: int
    pages: int

class ProductSearchItem(BaseModel):
    id: int
    full_name: str
    self: str

    class Config:
        from_attributes = True

class CartProduct(BaseModel):
    id: int
    name: str
    quantity: int
    price: float

class TelegramOrderRequest(BaseModel):
    phone: str
    source: Literal["buy_now", "cart"]
    items: List[CartProduct]

if TYPE_CHECKING:
    from schemas import ProductLineResponse, ProducerResponse, CategoryResponse