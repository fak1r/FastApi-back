from sqlalchemy import Column, Integer, String, Boolean
from database import Base

class User(Base):
  __tablename__ = "users"

  id = Column(Integer, primary_key=True, index=True)
  name = Column(String, nullable=False)
  email = Column(String, unique=True, nullable=False)
  hashed_password = Column(String, nullable=False)
  refresh_token = Column(String, nullable=True)
  is_admin = Column(Boolean, default=False)