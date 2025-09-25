"""Token deduction and validation middleware"""

from typing import Optional
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session

from app.models.token import UserToken, TokenType, TokenTransactionType
from app.models.template import Template
from app.services.token_service import TokenService
from database import get_db


async def verify_token_balance(
    request: Request,
    template_id: int,
    user_id: Optional[int] = None,
    db: Session = None
) -> bool:
    """
    Verify user has enough tokens for template
    Returns True if user has sufficient balance or is eligible for free document
    """
    if not db:
        db = next(get_db())

    # Get template token cost
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Skip token check for non-premium templates
    if not template.is_premium:
        return True

    # If no user_id (anonymous), only allow if template is free
    if not user_id:
        return template.token_cost == 0

    # Get user's token balance
    token_balance = db.query(UserToken).filter(
        UserToken.user_id == user_id
    ).first()

    # If no token record exists, user only has welcome bonus eligibility
    if not token_balance:
        # Check if user is eligible for welcome bonus
        if await TokenService.is_eligible_for_welcome_bonus(db, user_id):
            return True
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient token balance"
        )

    # Check if user has enough tokens
    if token_balance.document_tokens < template.token_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient token balance"
        )

    return True


async def deduct_tokens(
    request: Request,
    template_id: int,
    user_id: int,
    db: Session = None
) -> None:
    """Deduct tokens for template usage"""
    if not db:
        db = next(get_db())

    template = db.query(Template).filter(Template.id == template_id).first()
    if not template or not template.token_cost:
        return

    # Deduct tokens from user's balance
    await TokenService.deduct_tokens(
        db=db,
        user_id=user_id,
        token_type=TokenType.DOCUMENT_GENERATION,
        amount=template.token_cost,
        transaction_type=TokenTransactionType.SPENT,
        reference_id=template_id,
        reference_type="template"
    )