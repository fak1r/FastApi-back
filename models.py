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

  producers = relationship("Producer", back_populates="category")

class Producer(Base):
  __tablename__ = "producers"

  id = Column(Integer, primary_key=True, index=True)
  name = Column(String, nullable=False, unique=True)
  category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

  category = relationship("Category", back_populates="producers")
  product_lines = relationship("ProductLine", back_populates="producer")

class ProductLine(Base):
  __tablename__ = "product_lines"

  id = Column(Integer, primary_key=True, index=True)
  name = Column(String, nullable=False, unique=True)
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
  description = Column(String, nullable=True)
  price = Column(Float, nullable=False)
  product_line_id = Column(Integer, ForeignKey("product_lines.id"), nullable=False)
  favorite = Column(Boolean, default=False)
  details = Column(JSONB, nullable=True)

  product_line = relationship("ProductLine", back_populates="products")
  images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
