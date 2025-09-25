"""
Template pricing schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class PriceUpdate(BaseModel):
    """Schema for updating a single template's price"""
    new_price: float = Field(..., ge=0, description="New price in Naira")

class BulkPriceUpdate(BaseModel):
    """Schema for bulk price updates"""
    filter_type: str = Field(..., description="Filter by: 'all', 'category', 'tag', 'group'")
    filter_value: Optional[str] = Field(None, description="Value to filter by")
    price_change: float = Field(..., description="Amount to change price by")
    operation: str = Field(..., description="Operation: 'set', 'increase', 'decrease', 'percentage'")

class SpecialOffer(BaseModel):
    """Schema for special offers/discounts"""
    discount_percent: float = Field(..., ge=0, le=100, description="Discount percentage")
    start_date: datetime = Field(..., description="When the offer starts")
    end_date: datetime = Field(..., description="When the offer ends")
