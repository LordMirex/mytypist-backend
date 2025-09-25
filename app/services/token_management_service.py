"""
Advanced Token Management Service with Welcome Bonuses
Handles token distribution, campaigns, referrals, and automatic rewards
"""

import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.token import (
    UserToken, TokenTransaction, TokenCampaign, TokenReward,
    TokenType, TokenTransactionType
)
from app.models.user import User
from database import get_db

logger = logging.getLogger(__name__)


class TokenManagementService:
    """Advanced token management with welcome bonuses and campaigns"""

    # Default token amounts for different actions
    DEFAULT_WELCOME_BONUS = 50
    DEFAULT_REFERRAL_BONUS = 25
    DEFAULT_DOCUMENT_COST = 1
    DEFAULT_TEMPLATE_COST = 3
    DEFAULT_API_COST = 1

    @staticmethod
    def initialize_user_tokens(db: Session, user_id: int) -> UserToken:
        """Initialize token account for new user"""
        try:
            # Check if user already has tokens
            existing_tokens = db.query(UserToken).filter(
                UserToken.user_id == user_id
            ).first()
            
            if existing_tokens:
                return existing_tokens
            
            # Generate unique referral code
            referral_code = TokenManagementService._generate_referral_code()
            while db.query(UserToken).filter(UserToken.referral_code == referral_code).first():
                referral_code = TokenManagementService._generate_referral_code()
            
            # Create new token account
            user_tokens = UserToken(
                user_id=user_id,
                referral_code=referral_code,
                welcome_bonus_amount=TokenManagementService.DEFAULT_WELCOME_BONUS
            )
            
            db.add(user_tokens)
            db.commit()
            db.refresh(user_tokens)
            
            logger.info(f"Initialized token account for user {user_id}")
            return user_tokens
            
        except Exception as e:
            logger.error(f"Failed to initialize user tokens: {e}")
            raise

    @staticmethod
    def claim_welcome_bonus(db: Session, user_id: int) -> Dict[str, Any]:
        """Claim welcome bonus tokens for new user"""
        try:
            user_tokens = db.query(UserToken).filter(
                UserToken.user_id == user_id
            ).first()
            
            if not user_tokens:
                user_tokens = TokenManagementService.initialize_user_tokens(db, user_id)
            
            if not user_tokens.can_claim_welcome_bonus:
                return {
                    "success": False,
                    "message": "Welcome bonus already claimed"
                }
            
            # Check if user meets requirements (email verification, etc.)
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.email_verified:
                return {
                    "success": False,
                    "message": "Email verification required to claim welcome bonus"
                }
            
            # Award welcome bonus
            bonus_amount = user_tokens.welcome_bonus_amount
            
            success = TokenManagementService.add_tokens(
                db=db,
                user_id=user_id,
                token_type=TokenType.WELCOME_BONUS,
                amount=bonus_amount,
                description="Welcome bonus for new user",
                reference_type="welcome_bonus"
            )
            
            if success:
                # Mark welcome bonus as claimed
                user_tokens.welcome_bonus_claimed = True
                user_tokens.welcome_bonus_date = datetime.utcnow()
                user_tokens.document_tokens += bonus_amount
                db.commit()
                
                return {
                    "success": True,
                    "bonus_amount": bonus_amount,
                    "new_balance": user_tokens.total_tokens,
                    "message": f"Welcome bonus of {bonus_amount} tokens claimed!"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to process welcome bonus"
                }
                
        except Exception as e:
            logger.error(f"Failed to claim welcome bonus: {e}")
            return {
                "success": False,
                "message": "Internal error claiming welcome bonus"
            }

    @staticmethod
    def add_tokens(
        db: Session,
        user_id: int,
        token_type: TokenType,
        amount: int,
        description: str,
        reference_id: str = None,
        reference_type: str = None,
        campaign_id: str = None,
        bonus_multiplier: float = 1.0,
        expires_in_days: int = 365
    ) -> bool:
        """Add tokens to user account with transaction logging"""
        try:
            # Get or create user tokens
            user_tokens = db.query(UserToken).filter(
                UserToken.user_id == user_id
            ).first()
            
            if not user_tokens:
                user_tokens = TokenManagementService.initialize_user_tokens(db, user_id)
            
            # Calculate actual amount with multiplier
            actual_amount = int(amount * bonus_multiplier)
            
            # Get balance before transaction
            if token_type == TokenType.DOCUMENT_GENERATION:
                balance_before = user_tokens.document_tokens
                user_tokens.document_tokens += actual_amount
            elif token_type == TokenType.TEMPLATE_CREATION:
                balance_before = user_tokens.template_tokens
                user_tokens.template_tokens += actual_amount
            elif token_type == TokenType.API_USAGE:
                balance_before = user_tokens.api_tokens
                user_tokens.api_tokens += actual_amount
            elif token_type == TokenType.PREMIUM_FEATURES:
                balance_before = user_tokens.premium_tokens
                user_tokens.premium_tokens += actual_amount
            else:
                # Default to document tokens for bonuses
                balance_before = user_tokens.document_tokens
                user_tokens.document_tokens += actual_amount
            
            # Update lifetime stats
            user_tokens.lifetime_earned += actual_amount
            
            # Calculate expiry date
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            
            # Create transaction record
            transaction = TokenTransaction(
                user_id=user_id,
                transaction_type=TokenTransactionType.EARNED,
                token_type=token_type,
                amount=actual_amount,
                balance_before=balance_before,
                balance_after=balance_before + actual_amount,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type,
                campaign_id=campaign_id,
                bonus_multiplier=bonus_multiplier,
                expires_at=expires_at
            )
            
            db.add(transaction)
            db.commit()
            
            logger.info(f"Added {actual_amount} {token_type} tokens to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add tokens: {e}")
            db.rollback()
            return False

    @staticmethod
    def spend_tokens(
        db: Session,
        user_id: int,
        token_type: TokenType,
        amount: int,
        description: str,
        reference_id: str = None,
        reference_type: str = None
    ) -> Dict[str, Any]:
        """Spend tokens from user account"""
        try:
            user_tokens = db.query(UserToken).filter(
                UserToken.user_id == user_id
            ).first()
            
            if not user_tokens:
                return {
                    "success": False,
                    "message": "No token account found"
                }
            
            # Check if user has enough tokens
            if token_type == TokenType.DOCUMENT_GENERATION:
                current_balance = user_tokens.document_tokens
                if current_balance < amount:
                    return {
                        "success": False,
                        "message": f"Insufficient document tokens. Need {amount}, have {current_balance}"
                    }
                user_tokens.document_tokens -= amount
                
            elif token_type == TokenType.TEMPLATE_CREATION:
                current_balance = user_tokens.template_tokens
                if current_balance < amount:
                    return {
                        "success": False,
                        "message": f"Insufficient template tokens. Need {amount}, have {current_balance}"
                    }
                user_tokens.template_tokens -= amount
                
            elif token_type == TokenType.API_USAGE:
                current_balance = user_tokens.api_tokens
                if current_balance < amount:
                    return {
                        "success": False,
                        "message": f"Insufficient API tokens. Need {amount}, have {current_balance}"
                    }
                user_tokens.api_tokens -= amount
                
            else:
                return {
                    "success": False,
                    "message": f"Invalid token type for spending: {token_type}"
                }
            
            # Update lifetime stats
            user_tokens.lifetime_spent += amount
            user_tokens.monthly_used += amount
            
            # Create transaction record
            transaction = TokenTransaction(
                user_id=user_id,
                transaction_type=TokenTransactionType.SPENT,
                token_type=token_type,
                amount=-amount,  # Negative for spent
                balance_before=current_balance,
                balance_after=current_balance - amount,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type
            )
            
            db.add(transaction)
            db.commit()
            
            return {
                "success": True,
                "amount_spent": amount,
                "new_balance": current_balance - amount,
                "total_balance": user_tokens.total_tokens
            }
            
        except Exception as e:
            logger.error(f"Failed to spend tokens: {e}")
            db.rollback()
            return {
                "success": False,
                "message": "Internal error processing token spending"
            }

    @staticmethod
    def process_referral_bonus(db: Session, new_user_id: int, referral_code: str) -> Dict[str, Any]:
        """Process referral bonus for both referrer and new user"""
        try:
            # Find referrer by referral code
            referrer_tokens = db.query(UserToken).filter(
                UserToken.referral_code == referral_code
            ).first()
            
            if not referrer_tokens:
                return {
                    "success": False,
                    "message": "Invalid referral code"
                }
            
            referrer_id = referrer_tokens.user_id
            
            # Ensure new user is different from referrer
            if new_user_id == referrer_id:
                return {
                    "success": False,
                    "message": "Cannot refer yourself"
                }
            
            # Check if new user already has referral set
            new_user_tokens = db.query(UserToken).filter(
                UserToken.user_id == new_user_id
            ).first()
            
            if new_user_tokens and new_user_tokens.referred_by:
                return {
                    "success": False,
                    "message": "User already has a referrer"
                }
            
            # Set referral relationship
            if new_user_tokens:
                new_user_tokens.referred_by = referrer_id
            else:
                new_user_tokens = TokenManagementService.initialize_user_tokens(db, new_user_id)
                new_user_tokens.referred_by = referrer_id
            
            # Award bonus to referrer
            referrer_bonus = TokenManagementService.DEFAULT_REFERRAL_BONUS
            TokenManagementService.add_tokens(
                db=db,
                user_id=referrer_id,
                token_type=TokenType.REFERRAL_BONUS,
                amount=referrer_bonus,
                description=f"Referral bonus for referring user {new_user_id}",
                reference_id=str(new_user_id),
                reference_type="referral"
            )
            
            # Update referrer stats
            referrer_tokens.referral_bonus_earned += referrer_bonus
            
            # Award bonus to new user
            new_user_bonus = referrer_bonus // 2  # Half of referrer bonus
            TokenManagementService.add_tokens(
                db=db,
                user_id=new_user_id,
                token_type=TokenType.REFERRAL_BONUS,
                amount=new_user_bonus,
                description=f"Referral bonus for being referred by user {referrer_id}",
                reference_id=str(referrer_id),
                reference_type="referred"
            )
            
            db.commit()
            
            return {
                "success": True,
                "referrer_bonus": referrer_bonus,
                "new_user_bonus": new_user_bonus,
                "message": "Referral bonuses processed successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to process referral bonus: {e}")
            db.rollback()
            return {
                "success": False,
                "message": "Internal error processing referral"
            }

    @staticmethod
    def get_user_token_balance(db: Session, user_id: int) -> Dict[str, Any]:
        """Get comprehensive token balance and stats for user"""
        try:
            user_tokens = db.query(UserToken).filter(
                UserToken.user_id == user_id
            ).first()
            
            if not user_tokens:
                user_tokens = TokenManagementService.initialize_user_tokens(db, user_id)
            
            # Get recent transactions
            recent_transactions = db.query(TokenTransaction).filter(
                TokenTransaction.user_id == user_id
            ).order_by(desc(TokenTransaction.created_at)).limit(10).all()
            
            return {
                "success": True,
                "balances": {
                    "document_tokens": user_tokens.document_tokens,
                    "template_tokens": user_tokens.template_tokens,
                    "api_tokens": user_tokens.api_tokens,
                    "premium_tokens": user_tokens.premium_tokens,
                    "total_tokens": user_tokens.total_tokens
                },
                "lifetime_stats": {
                    "lifetime_earned": user_tokens.lifetime_earned,
                    "lifetime_spent": user_tokens.lifetime_spent,
                    "monthly_used": user_tokens.monthly_used,
                    "monthly_limit": user_tokens.monthly_limit
                },
                "referral_info": {
                    "referral_code": user_tokens.referral_code,
                    "referral_bonus_earned": user_tokens.referral_bonus_earned,
                    "referred_by": user_tokens.referred_by
                },
                "welcome_bonus": {
                    "claimed": user_tokens.welcome_bonus_claimed,
                    "claim_date": user_tokens.welcome_bonus_date.isoformat() if user_tokens.welcome_bonus_date else None,
                    "amount": user_tokens.welcome_bonus_amount,
                    "can_claim": user_tokens.can_claim_welcome_bonus
                },
                "recent_transactions": [
                    {
                        "id": t.id,
                        "type": t.transaction_type.value,
                        "token_type": t.token_type.value,
                        "amount": t.amount,
                        "description": t.description,
                        "created_at": t.created_at.isoformat()
                    }
                    for t in recent_transactions
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get token balance: {e}")
            return {
                "success": False,
                "message": "Failed to retrieve token balance"
            }

    @staticmethod
    def create_token_campaign(
        db: Session,
        admin_user_id: int,
        campaign_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new token campaign"""
        try:
            campaign = TokenCampaign(
                name=campaign_data["name"],
                description=campaign_data.get("description"),
                campaign_code=campaign_data["campaign_code"],
                token_type=TokenType(campaign_data["token_type"]),
                token_amount=campaign_data["token_amount"],
                bonus_multiplier=campaign_data.get("bonus_multiplier", 1.0),
                max_users=campaign_data.get("max_users"),
                max_tokens_per_user=campaign_data.get("max_tokens_per_user"),
                max_total_tokens=campaign_data.get("max_total_tokens"),
                starts_at=datetime.fromisoformat(campaign_data["starts_at"]),
                ends_at=datetime.fromisoformat(campaign_data["ends_at"]),
                min_account_age_days=campaign_data.get("min_account_age_days", 0),
                requires_email_verification=campaign_data.get("requires_email_verification", True),
                requires_phone_verification=campaign_data.get("requires_phone_verification", False),
                created_by=admin_user_id
            )
            
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            
            return {
                "success": True,
                "campaign_id": campaign.id,
                "message": "Campaign created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create campaign: {e}")
            db.rollback()
            return {
                "success": False,
                "message": f"Failed to create campaign: {str(e)}"
            }

    @staticmethod
    def reset_monthly_limits(db: Session):
        """Reset monthly token usage limits (called by scheduled task)"""
        try:
            current_date = datetime.utcnow()
            
            # Find accounts that need monthly reset
            accounts_to_reset = db.query(UserToken).filter(
                UserToken.monthly_used > 0,
                UserToken.last_monthly_reset.is_(None) |
                (UserToken.last_monthly_reset < current_date - timedelta(days=30))
            ).all()
            
            reset_count = 0
            for account in accounts_to_reset:
                account.monthly_used = 0
                account.last_monthly_reset = current_date
                reset_count += 1
            
            db.commit()
            logger.info(f"Reset monthly limits for {reset_count} accounts")
            
        except Exception as e:
            logger.error(f"Failed to reset monthly limits: {e}")
            db.rollback()

    @staticmethod
    def _generate_referral_code(length: int = 8) -> str:
        """Generate unique referral code"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))

    @staticmethod
    def award_activity_tokens(db: Session, user_id: int, activity_type: str) -> bool:
        """Award tokens for user activities"""
        activity_rewards = {
            "document_created": (TokenType.DOCUMENT_GENERATION, 2),
            "template_created": (TokenType.TEMPLATE_CREATION, 5),
            "first_login": (TokenType.WELCOME_BONUS, 10),
            "email_verified": (TokenType.WELCOME_BONUS, 5),
            "profile_completed": (TokenType.WELCOME_BONUS, 15),
        }
        
        if activity_type not in activity_rewards:
            return False
        
        token_type, amount = activity_rewards[activity_type]
        
        return TokenManagementService.add_tokens(
            db=db,
            user_id=user_id,
            token_type=token_type,
            amount=amount,
            description=f"Activity reward: {activity_type.replace('_', ' ').title()}",
            reference_type="activity_reward"
        )