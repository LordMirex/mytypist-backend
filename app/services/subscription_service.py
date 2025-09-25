"""
Subscription Management and Token Allocation Service
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional

from app.models.subscription import SubscriptionPlan, UserSubscription, SubscriptionStatus
from app.models.token import UserToken, TokenTransactionType, TokenType
from app.models.user import User


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db

    async def allocate_subscription_tokens(self, user_id: int) -> bool:
        """
        Allocate monthly tokens based on user's subscription plan
        Returns True if tokens were allocated, False if no allocation was needed
        """
        # Get user's active subscription
        subscription = (
            self.db.query(UserSubscription)
            .filter(
                UserSubscription.user_id == user_id,
                UserSubscription.status == SubscriptionStatus.ACTIVE,
                UserSubscription.end_date > datetime.now(timezone.utc)
            )
            .first()
        )

        if not subscription:
            return False

        # Check if it's time for new token allocation
        now = datetime.now(timezone.utc)
        if (not subscription.last_token_allocation or 
            now >= subscription.next_token_allocation):
            
            # Get subscription plan details
            plan = subscription.plan

            # Get or create user token record
            user_tokens = (
                self.db.query(UserToken)
                .filter(UserToken.user_id == user_id)
                .first()
            )
            
            if not user_tokens:
                user_tokens = UserToken(user_id=user_id)
                self.db.add(user_tokens)

            # Allocate tokens based on plan
            user_tokens.document_tokens += plan.monthly_document_tokens
            user_tokens.template_tokens += plan.monthly_template_tokens
            user_tokens.api_tokens += plan.monthly_api_tokens
            user_tokens.premium_tokens += plan.monthly_premium_tokens

            # Update lifetime earned
            total_tokens = (
                plan.monthly_document_tokens +
                plan.monthly_template_tokens +
                plan.monthly_api_tokens +
                plan.monthly_premium_tokens
            )
            user_tokens.lifetime_earned += total_tokens

            # Update subscription tracking
            subscription.last_token_allocation = now
            subscription.next_token_allocation = self._calculate_next_allocation(subscription)

            self.db.commit()
            return True

        return False

    def _calculate_next_allocation(self, subscription: UserSubscription) -> datetime:
        """Calculate the next token allocation date based on billing cycle"""
        # If we're in the middle of a billing cycle, next allocation is at the start of next cycle
        now = datetime.now(timezone.utc)
        if now < subscription.billing_cycle_end:
            return subscription.billing_cycle_end
        return subscription.next_token_allocation