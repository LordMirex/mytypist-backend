"""
Template pricing routes
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_admin_user
from app.models.user import User
from app.schemas.template_pricing import PriceUpdate, BulkPriceUpdate, SpecialOffer
from app.services.template_service import TemplateService
from database import get_db

router = APIRouter()

@router.put("/templates/{template_id}/price", response_model=Dict[str, Any])
async def update_template_price(
    template_id: int,
    price_update: PriceUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update price for a single template"""
    try:
        template = await TemplateService.update_template_price(db, template_id, price_update.new_price)
        return {
            "status": "success",
            "template_id": template.id,
            "new_price": template.price
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update price: {str(e)}")

@router.post("/templates/price/bulk", response_model=Dict[str, Any])
async def update_bulk_prices(
    price_update: BulkPriceUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update prices in bulk for templates"""
    try:
        updated = await TemplateService.bulk_update_prices(
            db,
            price_update.filter_type,
            price_update.filter_value,
            price_update.price_change,
            price_update.operation
        )
        return {
            "status": "success",
            "updated_count": updated,
            "message": f"Successfully updated {updated} template prices"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update prices: {str(e)}")

@router.post("/templates/{template_id}/special-offer", response_model=Dict[str, Any])
async def set_special_offer(
    template_id: int,
    offer: SpecialOffer,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Set a special offer/discount for a template"""
    try:
        template = await TemplateService.set_special_offer(
            db,
            template_id,
            offer.discount_percent,
            offer.start_date,
            offer.end_date
        )
        return {
            "status": "success",
            "template_id": template.id,
            "original_price": template.special_offer["original_price"],
            "discounted_price": template.price,
            "discount_percent": offer.discount_percent,
            "offer_ends": offer.end_date.isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set special offer: {str(e)}")
