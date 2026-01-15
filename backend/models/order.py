from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, JSON
from sqlalchemy.sql import func
from core.database import Base
from enum import Enum as PyEnum
import enum

class OrderStatus(str, PyEnum):
    NEW = "new"
    COOKING = "cooking"
    READY = "ready"
    SERVED = "served"
    CANCELLED = "cancelled"

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    table_num = Column(Integer, nullable=False, index=True)
    items = Column(JSON, nullable=False)  # [{"name": "Idly", "qty": 3, "price": 95}]
    total_amount = Column(Float, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW, index=True)
    raw_text = Column(String)
    cleaned_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
