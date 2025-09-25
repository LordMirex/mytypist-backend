"""
Wallet Service
User wallet management for credits, transactions, and premium features
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, JSON, func, desc, and_
from sqlalchemy.orm import relationship
from enum import Enum

from database import Base
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.payment_service import PaymentService


class TransactionType(str, Enum):
    """Wallet transaction types"""
    CREDIT = "credit"           # Money added to wallet
    DEBIT = "debit"             # Money spent from wallet
    REFUND = "refund"           # Money refunded to wallet
    BONUS = "bonus"             # Promotional credits
    PENALTY = "penalty"         # Deductions for violations
    TRANSFER_IN = "transfer_in" # Received from another user
    TRANSFER_OUT = "transfer_out" # Sent to another user


class TransactionStatus(str, Enum):
    """Transaction status"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Wallet(Base):
    """User wallet model"""
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True, index=True)

    # Balance information
    balance = Column(Float, nullable=False, default=0.0)  # Available balance
    pending_balance = Column(Float, nullable=False, default=0.0)  # Pending transactions
    total_earned = Column(Float, nullable=False, default=0.0)  # Lifetime earnings
    total_spent = Column(Float, nullable=False, default=0.0)  # Lifetime spending

    # Wallet settings
    currency = Column(String(3), nullable=False, default="NGN")
    is_active = Column(Boolean, nullable=False, default=True)
    is_frozen = Column(Boolean, nullable=False, default=False)

    # Security
    pin_hash = Column(String(255), nullable=True)  # Optional wallet PIN
    last_transaction_at = Column(DateTime, nullable=True)

    # Limits and controls
    daily_spend_limit = Column(Float, nullable=True)  # Daily spending limit
    monthly_spend_limit = Column(Float, nullable=True)  # Monthly spending limit
    daily_spent = Column(Float, nullable=False, default=0.0)  # Today's spending
    monthly_spent = Column(Float, nullable=False, default=0.0)  # This month's spending
    last_reset_date = Column(DateTime, nullable=True)  # Last limit reset

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="wallet")


class WalletTransaction(Base):
    """Wallet transaction history"""
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False, index=True)

    # Transaction details
    transaction_type = Column(String(20), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="NGN")
    status = Column(String(20), nullable=False, default=TransactionStatus.PENDING, index=True)

    # Description and metadata
    description = Column(String(500), nullable=False)
    reference = Column(String(100), nullable=True, unique=True, index=True)  # External reference
    transaction_metadata = Column(JSON, nullable=True)  # Additional transaction data

    # Related entities
    related_payment_id = Column(Integer, nullable=True)  # Related payment record
    related_template_id = Column(Integer, nullable=True)  # Template purchase
    related_document_id = Column(Integer, nullable=True)  # Document-related transaction
    related_user_id = Column(Integer, nullable=True)  # For transfers

    # Balance tracking
    balance_before = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)

    # Processing information
    processed_at = Column(DateTime, nullable=True)
    failed_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    wallet = relationship("Wallet", backref="transactions")


class WalletService:
    """Wallet management service"""

    @staticmethod
    def get_or_create_wallet(db: Session, user_id: int) -> Wallet:
        """Get user's wallet or create if doesn't exist"""

        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if not wallet:
            wallet = Wallet(user_id=user_id)
            db.add(wallet)
            db.commit()
            db.refresh(wallet)

            # Log wallet creation
            AuditService.log_system_event(
                "WALLET_CREATED",
                {"user_id": user_id, "wallet_id": wallet.id}
            )

        return wallet

    @staticmethod
    def get_wallet_balance(db: Session, user_id: int) -> Dict:
        """Get wallet balance information"""

        wallet = WalletService.get_or_create_wallet(db, user_id)

        # Reset daily/monthly limits if needed
        WalletService._reset_spending_limits(db, wallet)

        return {
            "wallet_id": wallet.id,
            "balance": wallet.balance,
            "pending_balance": wallet.pending_balance,
            "total_earned": wallet.total_earned,
            "total_spent": wallet.total_spent,
            "currency": wallet.currency,
            "is_active": wallet.is_active,
            "is_frozen": wallet.is_frozen,
            "daily_spend_limit": wallet.daily_spend_limit,
            "monthly_spend_limit": wallet.monthly_spend_limit,
            "daily_spent": wallet.daily_spent,
            "monthly_spent": wallet.monthly_spent,
            "last_transaction_at": wallet.last_transaction_at
        }

    @staticmethod
    def add_funds(db: Session, user_id: int, amount: float, description: str,
                  reference: str = None, metadata: Dict = None) -> Dict:
        """Add funds to user's wallet"""

        if amount <= 0:
            return {"success": False, "error": "Amount must be positive"}

        wallet = WalletService.get_or_create_wallet(db, user_id)

        if wallet.is_frozen:
            return {"success": False, "error": "Wallet is frozen"}

        # Create transaction
        transaction = WalletTransaction(
            wallet_id=wallet.id,
            transaction_type=TransactionType.CREDIT,
            amount=amount,
            currency=wallet.currency,
            description=description,
            reference=reference,
            metadata=metadata,
            balance_before=wallet.balance,
            balance_after=wallet.balance + amount,
            status=TransactionStatus.COMPLETED,
            processed_at=datetime.utcnow()
        )

        # Update wallet balance
        wallet.balance += amount
        wallet.total_earned += amount
        wallet.last_transaction_at = datetime.utcnow()

        db.add(transaction)
        db.commit()

        # Log transaction
        AuditService.log_system_event(
            "WALLET_CREDIT",
            {
                "user_id": user_id,
                "wallet_id": wallet.id,
                "amount": amount,
                "transaction_id": transaction.id,
                "new_balance": wallet.balance
            }
        )

        return {
            "success": True,
            "transaction_id": transaction.id,
            "new_balance": wallet.balance,
            "amount": amount
        }

    @staticmethod
    def deduct_funds(db: Session, user_id: int, amount: float, description: str,
                    reference: str = None, metadata: Dict = None,
                    related_template_id: int = None, related_document_id: int = None) -> Dict:
        """Deduct funds from user's wallet"""

        if amount <= 0:
            return {"success": False, "error": "Amount must be positive"}

        wallet = WalletService.get_or_create_wallet(db, user_id)

        if wallet.is_frozen:
            return {"success": False, "error": "Wallet is frozen"}

        if wallet.balance < amount:
            return {"success": False, "error": "Insufficient balance"}

        # Check spending limits
        limit_check = WalletService._check_spending_limits(db, wallet, amount)
        if not limit_check["allowed"]:
            return {"success": False, "error": limit_check["reason"]}

        # Create transaction
        transaction = WalletTransaction(
            wallet_id=wallet.id,
            transaction_type=TransactionType.DEBIT,
            amount=amount,
            currency=wallet.currency,
            description=description,
            reference=reference,
            metadata=metadata,
            related_template_id=related_template_id,
            related_document_id=related_document_id,
            balance_before=wallet.balance,
            balance_after=wallet.balance - amount,
            status=TransactionStatus.COMPLETED,
            processed_at=datetime.utcnow()
        )

        # Update wallet balance
        wallet.balance -= amount
        wallet.total_spent += amount
        wallet.daily_spent += amount
        wallet.monthly_spent += amount
        wallet.last_transaction_at = datetime.utcnow()

        db.add(transaction)
        db.commit()

        # Log transaction
        AuditService.log_system_event(
            "WALLET_DEBIT",
            {
                "user_id": user_id,
                "wallet_id": wallet.id,
                "amount": amount,
                "transaction_id": transaction.id,
                "new_balance": wallet.balance
            }
        )

        return {
            "success": True,
            "transaction_id": transaction.id,
            "new_balance": wallet.balance,
            "amount": amount
        }

    @staticmethod
    def transfer_funds(db: Session, from_user_id: int, to_user_id: int, amount: float,
                      description: str, reference: str = None) -> Dict:
        """Transfer funds between users"""

        if amount <= 0:
            return {"success": False, "error": "Amount must be positive"}

        if from_user_id == to_user_id:
            return {"success": False, "error": "Cannot transfer to yourself"}

        from_wallet = WalletService.get_or_create_wallet(db, from_user_id)
        to_wallet = WalletService.get_or_create_wallet(db, to_user_id)

        if from_wallet.is_frozen or to_wallet.is_frozen:
            return {"success": False, "error": "One or both wallets are frozen"}

        if from_wallet.balance < amount:
            return {"success": False, "error": "Insufficient balance"}

        # Check spending limits for sender
        limit_check = WalletService._check_spending_limits(db, from_wallet, amount)
        if not limit_check["allowed"]:
            return {"success": False, "error": limit_check["reason"]}

        try:
            # Create outgoing transaction
            out_transaction = WalletTransaction(
                wallet_id=from_wallet.id,
                transaction_type=TransactionType.TRANSFER_OUT,
                amount=amount,
                currency=from_wallet.currency,
                description=f"Transfer to user {to_user_id}: {description}",
                reference=reference,
                related_user_id=to_user_id,
                balance_before=from_wallet.balance,
                balance_after=from_wallet.balance - amount,
                status=TransactionStatus.COMPLETED,
                processed_at=datetime.utcnow()
            )

            # Create incoming transaction
            in_transaction = WalletTransaction(
                wallet_id=to_wallet.id,
                transaction_type=TransactionType.TRANSFER_IN,
                amount=amount,
                currency=to_wallet.currency,
                description=f"Transfer from user {from_user_id}: {description}",
                reference=reference,
                related_user_id=from_user_id,
                balance_before=to_wallet.balance,
                balance_after=to_wallet.balance + amount,
                status=TransactionStatus.COMPLETED,
                processed_at=datetime.utcnow()
            )

            # Update wallet balances
            from_wallet.balance -= amount
            from_wallet.total_spent += amount
            from_wallet.daily_spent += amount
            from_wallet.monthly_spent += amount
            from_wallet.last_transaction_at = datetime.utcnow()

            to_wallet.balance += amount
            to_wallet.total_earned += amount
            to_wallet.last_transaction_at = datetime.utcnow()

            db.add(out_transaction)
            db.add(in_transaction)
            db.commit()

            # Log transfer
            AuditService.log_system_event(
                "WALLET_TRANSFER",
                {
                    "from_user_id": from_user_id,
                    "to_user_id": to_user_id,
                    "amount": amount,
                    "out_transaction_id": out_transaction.id,
                    "in_transaction_id": in_transaction.id
                }
            )

            return {
                "success": True,
                "out_transaction_id": out_transaction.id,
                "in_transaction_id": in_transaction.id,
                "sender_balance": from_wallet.balance,
                "recipient_balance": to_wallet.balance
            }

        except Exception as e:
            db.rollback()
            return {"success": False, "error": f"Transfer failed: {str(e)}"}

    @staticmethod
    def refund_transaction(db: Session, transaction_id: int, reason: str = None) -> Dict:
        """Refund a wallet transaction"""

        transaction = db.query(WalletTransaction).filter(
            WalletTransaction.id == transaction_id
        ).first()

        if not transaction:
            return {"success": False, "error": "Transaction not found"}

        if transaction.status != TransactionStatus.COMPLETED:
            return {"success": False, "error": "Only completed transactions can be refunded"}

        if transaction.transaction_type != TransactionType.DEBIT:
            return {"success": False, "error": "Only debit transactions can be refunded"}

        wallet = transaction.wallet

        # Create refund transaction
        refund_transaction = WalletTransaction(
            wallet_id=wallet.id,
            transaction_type=TransactionType.REFUND,
            amount=transaction.amount,
            currency=transaction.currency,
            description=f"Refund for: {transaction.description}",
            reference=f"REFUND_{transaction.id}",
            metadata={"original_transaction_id": transaction.id, "reason": reason},
            balance_before=wallet.balance,
            balance_after=wallet.balance + transaction.amount,
            status=TransactionStatus.COMPLETED,
            processed_at=datetime.utcnow()
        )

        # Update wallet balance
        wallet.balance += transaction.amount
        wallet.last_transaction_at = datetime.utcnow()

        # Mark original transaction as refunded
        transaction.status = TransactionStatus.REFUNDED

        db.add(refund_transaction)
        db.commit()

        # Log refund
        AuditService.log_system_event(
            "WALLET_REFUND",
            {
                "user_id": wallet.user_id,
                "wallet_id": wallet.id,
                "amount": transaction.amount,
                "original_transaction_id": transaction.id,
                "refund_transaction_id": refund_transaction.id,
                "reason": reason
            }
        )

        return {
            "success": True,
            "refund_transaction_id": refund_transaction.id,
            "amount": transaction.amount,
            "new_balance": wallet.balance
        }

    @staticmethod
    def get_transaction_history(db: Session, user_id: int, page: int = 1, per_page: int = 20,
                               transaction_type: str = None, start_date: datetime = None,
                               end_date: datetime = None) -> Dict:
        """Get wallet transaction history"""

        wallet = WalletService.get_or_create_wallet(db, user_id)

        query = db.query(WalletTransaction).filter(
            WalletTransaction.wallet_id == wallet.id
        ).order_by(desc(WalletTransaction.created_at))

        # Apply filters
        if transaction_type:
            query = query.filter(WalletTransaction.transaction_type == transaction_type)

        if start_date:
            query = query.filter(WalletTransaction.created_at >= start_date)

        if end_date:
            query = query.filter(WalletTransaction.created_at <= end_date)

        # Get total count
        total = query.count()

        # Apply pagination
        transactions = query.offset((page - 1) * per_page).limit(per_page).all()

        return {
            "transactions": [WalletService._format_transaction(t) for t in transactions],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page
        }

    @staticmethod
    def set_spending_limits(db: Session, user_id: int, daily_limit: float = None,
                           monthly_limit: float = None) -> Dict:
        """Set wallet spending limits"""

        wallet = WalletService.get_or_create_wallet(db, user_id)

        if daily_limit is not None:
            wallet.daily_spend_limit = daily_limit if daily_limit > 0 else None

        if monthly_limit is not None:
            wallet.monthly_spend_limit = monthly_limit if monthly_limit > 0 else None

        db.commit()

        return {
            "success": True,
            "daily_limit": wallet.daily_spend_limit,
            "monthly_limit": wallet.monthly_spend_limit
        }

    @staticmethod
    def freeze_wallet(db: Session, user_id: int, reason: str = None) -> Dict:
        """Freeze user's wallet"""

        wallet = WalletService.get_or_create_wallet(db, user_id)
        wallet.is_frozen = True
        db.commit()

        # Log freeze action
        AuditService.log_system_event(
            "WALLET_FROZEN",
            {
                "user_id": user_id,
                "wallet_id": wallet.id,
                "reason": reason
            }
        )

        return {"success": True, "message": "Wallet frozen successfully"}

    @staticmethod
    def unfreeze_wallet(db: Session, user_id: int, reason: str = None) -> Dict:
        """Unfreeze user's wallet"""

        wallet = WalletService.get_or_create_wallet(db, user_id)
        wallet.is_frozen = False
        db.commit()

        # Log unfreeze action
        AuditService.log_system_event(
            "WALLET_UNFROZEN",
            {
                "user_id": user_id,
                "wallet_id": wallet.id,
                "reason": reason
            }
        )

        return {"success": True, "message": "Wallet unfrozen successfully"}

    @staticmethod
    def _check_spending_limits(db: Session, wallet: Wallet, amount: float) -> Dict:
        """Check if transaction is within spending limits"""

        # Reset limits if needed
        WalletService._reset_spending_limits(db, wallet)

        # Check daily limit
        if wallet.daily_spend_limit and (wallet.daily_spent + amount) > wallet.daily_spend_limit:
            return {
                "allowed": False,
                "reason": f"Daily spending limit of {wallet.daily_spend_limit} {wallet.currency} exceeded"
            }

        # Check monthly limit
        if wallet.monthly_spend_limit and (wallet.monthly_spent + amount) > wallet.monthly_spend_limit:
            return {
                "allowed": False,
                "reason": f"Monthly spending limit of {wallet.monthly_spend_limit} {wallet.currency} exceeded"
            }

        return {"allowed": True}

    @staticmethod
    def _reset_spending_limits(db: Session, wallet: Wallet):
        """Reset daily/monthly spending limits if period has passed"""

        now = datetime.utcnow()
        today = now.date()

        # Reset daily limit
        if wallet.last_reset_date is None or wallet.last_reset_date.date() < today:
            wallet.daily_spent = 0.0

        # Reset monthly limit
        current_month = (now.year, now.month)
        last_reset_month = None
        if wallet.last_reset_date:
            last_reset_month = (wallet.last_reset_date.year, wallet.last_reset_date.month)

        if last_reset_month != current_month:
            wallet.monthly_spent = 0.0

        wallet.last_reset_date = now
        db.commit()

    @staticmethod
    def _format_transaction(transaction: WalletTransaction) -> Dict:
        """Format transaction for API response"""
        return {
            "id": transaction.id,
            "type": transaction.transaction_type,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status,
            "description": transaction.description,
            "reference": transaction.reference,
            "balance_before": transaction.balance_before,
            "balance_after": transaction.balance_after,
            "metadata": transaction.transaction_metadata,
            "related_template_id": transaction.related_template_id,
            "related_document_id": transaction.related_document_id,
            "related_user_id": transaction.related_user_id,
            "created_at": transaction.created_at,
            "processed_at": transaction.processed_at,
            "failed_reason": transaction.failed_reason
        }

    @staticmethod
    def get_wallet_statistics(db: Session, user_id: int, days: int = 30) -> Dict:
        """Get wallet usage statistics"""

        wallet = WalletService.get_or_create_wallet(db, user_id)
        start_date = datetime.utcnow() - timedelta(days=days)

        # Transaction counts by type
        transaction_stats = db.query(
            WalletTransaction.transaction_type,
            func.count(WalletTransaction.id).label('count'),
            func.sum(WalletTransaction.amount).label('total_amount')
        ).filter(
            WalletTransaction.wallet_id == wallet.id,
            WalletTransaction.created_at >= start_date,
            WalletTransaction.status == TransactionStatus.COMPLETED
        ).group_by(WalletTransaction.transaction_type).all()

        # Daily spending trend
        daily_spending = db.query(
            func.date(WalletTransaction.created_at).label('date'),
            func.sum(WalletTransaction.amount).label('amount')
        ).filter(
            WalletTransaction.wallet_id == wallet.id,
            WalletTransaction.transaction_type == TransactionType.DEBIT,
            WalletTransaction.created_at >= start_date,
            WalletTransaction.status == TransactionStatus.COMPLETED
        ).group_by(func.date(WalletTransaction.created_at)).all()

        return {
            "wallet_info": WalletService.get_wallet_balance(db, user_id),
            "period_days": days,
            "transaction_stats": [
                {
                    "type": stat.transaction_type,
                    "count": stat.count,
                    "total_amount": stat.total_amount or 0
                }
                for stat in transaction_stats
            ],
            "daily_spending": [
                {
                    "date": str(day.date),
                    "amount": day.amount or 0
                }
                for day in daily_spending
            ]
        }
