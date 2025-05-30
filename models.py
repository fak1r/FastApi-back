from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, unique=True, index=True)

    producers = relationship("Producer", back_populates="category")

class Producer(Base):
    __tablename__ = "producers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, unique=True, index=True) 
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

    category = relationship("Category", back_populates="producers")
    product_lines = relationship("ProductLine", back_populates="producer")

class ProductLine(Base):
    __tablename__ = "product_lines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, unique=True, index=True)
    producer_id = Column(Integer, ForeignKey("producers.id"), nullable=False)

    producer = relationship("Producer", back_populates="product_lines")
    products = relationship("Product", back_populates="product_line")

class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    image_url = Column(String, nullable=False)

    product = relationship("Product", back_populates="images")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    slug = Column(String, unique=True, index=True)
    product_line_id = Column(Integer, ForeignKey("product_lines.id"), nullable=False)
    price = Column(Float, nullable=False)
    img_mini = Column(JSONB, nullable=True)
    rating = Column(Float, default=0.0)
    favorite = Column(Boolean, default=False)
    details = Column(JSONB, nullable=True)

    product_line = relationship("ProductLine", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_phone = Column(String, nullable=False)
    source = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False, default=0.0)
    items_json = Column(JSONB, nullable=True) 

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")