from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class Item(BaseModel):
    name: str = Field(..., min_length=1)
    qty: int = Field(..., ge=1)
    price: float = Field(..., gt=0)

class CleanOrder(BaseModel):
    table_num: int = Field(..., ge=1, le=20)
    items: List[Item] = Field(..., min_items=1)
    total_amount: float = Field(..., gt=0)
    
    class Config:
        from_attributes = True

class OrderInput(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=500)

class ErrorResponse(BaseModel):
    error: str
    suggestion: str

class OrderStatusUpdate(BaseModel):
    status: str
