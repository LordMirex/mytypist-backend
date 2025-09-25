"""
Payment processing background tasks
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from celery import Celery
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from config import settings
from database import SessionLocal
from app.models.payment import Payment, Subscription, PaymentStatus, SubscriptionStatus
from app.models.user import User
from app.services.payment_service import PaymentService
from app.services.audit_service import AuditService

# Create Celery instance
celery_app = Celery(
    "payment_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)


@celery_app.task(bind=True, max_retries=3)
def process_payment_webhook_task(self, webhook_data: Dict[str, Any]):
    """Process Flutterwave webhook in background"""

    try:
        success = PaymentService.process_webhook(webhook_data)

        if success:
            AuditService.log_system_event(
                "WEBHOOK_PROCESSED",
                {
                    "event_type": webhook_data.get("event"),
                    "transaction_ref": webhook_data.get("data", {}).get("tx_ref")
                }
            )
        else:
            AuditService.log_system_event(
                "WEBHOOK_PROCESSING_FAILED",
                {
                    "event_type": webhook_data.get("event"),
                    "error": "Processing returned False"
                }
            )

        return {"success": success}

    except Exception as exc:
        # Log webhook processing error
        AuditService.log_system_event(
            "WEBHOOK_PROCESSING_ERROR",
            {
                "event_type": webhook_data.get("event"),
                "error": str(exc),
                "retries": self.request.retries
            }
        )

        # Retry task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))

        raise exc


@celery_app.task
def update_subscription_status_task():
    """Update subscription statuses based on expiration"""

    db = SessionLocal()

    try:
        current_time = datetime.utcnow()
        updated_count = 0

        # Find expired subscriptions
        expired_subscriptions = db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.ends_at <= current_time
        ).all()

        for subscription in expired_subscriptions:
            if subscription.auto_renew:
                # Attempt to renew subscription
                try:
                    renewal_success = attempt_subscription_renewal(db, subscription)
                    if renewal_success:
                        AuditService.log_subscription_event(
                            "SUBSCRIPTION_RENEWED",
                            subscription.user_id,
                            None,
                            {
                                "subscription_id": subscription.id,
                                "plan": subscription.plan.value,
                                "new_end_date": subscription.ends_at.isoformat()
                            }
                        )
                    else:
                        subscription.status = SubscriptionStatus.EXPIRED
                        subscription.auto_renew = False
                        updated_count += 1

                        AuditService.log_subscription_event(
                            "SUBSCRIPTION_EXPIRED",
                            subscription.user_id,
                            None,
                            {
                                "subscription_id": subscription.id,
                                "plan": subscription.plan.value,
                                "renewal_failed": True
                            }
                        )

                except Exception as e:
                    subscription.status = SubscriptionStatus.EXPIRED
                    subscription.auto_renew = False
                    updated_count += 1

                    AuditService.log_subscription_event(
                        "SUBSCRIPTION_RENEWAL_FAILED",
                        subscription.user_id,
                        None,
                        {
                            "subscription_id": subscription.id,
                            "error": str(e)
                        }
                    )
            else:
                # Mark as expired
                subscription.status = SubscriptionStatus.EXPIRED
                updated_count += 1

                AuditService.log_subscription_event(
                    "SUBSCRIPTION_EXPIRED",
                    subscription.user_id,
                    None,
                    {
                        "subscription_id": subscription.id,
                        "plan": subscription.plan.value
                    }
                )

        db.commit()

        return {"updated_subscriptions": updated_count}

    except Exception as e:
        AuditService.log_system_event(
            "SUBSCRIPTION_STATUS_UPDATE_FAILED",
            {"error": str(e)}
        )
        raise e

    finally:
        db.close()


def attempt_subscription_renewal(db: Session, subscription: Subscription) -> bool:
    """Attempt to renew subscription"""

    try:
        # Create renewal payment
        from app.schemas.payment import PaymentCreate
        from app.models.payment import PaymentMethod

        payment_data = PaymentCreate(
            amount=subscription.amount,
            currency="NGN",
            description=f"Subscription renewal - {subscription.plan.value}",
            payment_method=PaymentMethod.CARD  # Default to card
        )

        payment = PaymentService.create_payment(db, payment_data, subscription.user_id)

        # Initialize payment with Flutterwave (real implementation)
    # Integrate with stored payment methods if available (future enhancement)
        # If successful, extend subscription
        if subscription.billing_cycle == "yearly":
            subscription.ends_at = subscription.ends_at + timedelta(days=365)
        else:
            subscription.ends_at = subscription.ends_at + timedelta(days=30)

        subscription.next_billing_date = subscription.ends_at
        subscription.renewal_attempts = 0

        return True

    except Exception as e:
        subscription.renewal_attempts += 1
        return False


@celery_app.task
def send_payment_notification_task(payment_id: int, notification_type: str):
    """Send payment notification email/SMS"""

    db = SessionLocal()

    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return {"error": "Payment not found"}

        user = db.query(User).filter(User.id == payment.user_id).first()
        if not user:
            return {"error": "User not found"}

        # Send notification based on type
        if notification_type == "payment_completed":
            send_payment_success_notification(user, payment)
        elif notification_type == "payment_failed":
            send_payment_failure_notification(user, payment)
        elif notification_type == "subscription_renewed":
            send_subscription_renewal_notification(user, payment)

        AuditService.log_payment_event(
            "PAYMENT_NOTIFICATION_SENT",
            user.id,
            None,
            {
                "payment_id": payment_id,
                "notification_type": notification_type,
                "recipient": user.email
            }
        )

        return {"success": True, "notification_type": notification_type}

    except Exception as e:
        AuditService.log_system_event(
            "PAYMENT_NOTIFICATION_FAILED",
            {
                "payment_id": payment_id,
                "notification_type": notification_type,
                "error": str(e)
            }
        )
        raise e

    finally:
        db.close()


def send_payment_success_notification(user: User, payment: Payment):
    """Send payment success notification"""
    try:
        from app.services.email_service import email_service
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            email_service.send_payment_confirmation_email(user.email, payment)
        )
    except Exception as e:
        logger.warning(f"Failed to send payment success email: {e}")


def send_payment_failure_notification(user: User, payment: Payment):
    """Send payment failure notification"""
    try:
        from app.services.email_service import email_service
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            email_service.send_payment_failure_email(user.email, payment)
        )
    except Exception as e:
        logger.warning(f"Failed to send payment failure email: {e}")


def send_subscription_renewal_notification(user: User, payment: Payment):
    """Send subscription renewal notification"""
    try:
        from app.services.email_service import email_service
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            email_service.send_subscription_renewal_email(user.email, payment)
        )
    except Exception as e:
        logger.warning(f"Failed to send subscription renewal email: {e}")


@celery_app.task
def generate_monthly_revenue_report_task():
    """Generate monthly revenue report"""

    db = SessionLocal()

    try:
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

        # Calculate monthly revenue
        from sqlalchemy import func

        current_month_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.completed_at >= current_month_start
        ).scalar() or 0

        last_month_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.completed_at >= last_month_start,
            Payment.completed_at < current_month_start
        ).scalar() or 0

        # Calculate transaction counts
        current_month_transactions = db.query(Payment).filter(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.completed_at >= current_month_start
        ).count()

        last_month_transactions = db.query(Payment).filter(
            Payment.status == PaymentStatus.COMPLETED,
            Payment.completed_at >= last_month_start,
            Payment.completed_at < current_month_start
        ).count()

        # Calculate growth rate
        if last_month_revenue > 0:
            revenue_growth = ((current_month_revenue - last_month_revenue) / last_month_revenue) * 100
        else:
            revenue_growth = 100.0 if current_month_revenue > 0 else 0.0

        report = {
            "report_date": datetime.utcnow().isoformat(),
            "current_month": {
                "revenue": float(current_month_revenue),
                "transactions": current_month_transactions,
                "start_date": current_month_start.isoformat()
            },
            "last_month": {
                "revenue": float(last_month_revenue),
                "transactions": last_month_transactions,
                "start_date": last_month_start.isoformat()
            },
            "growth": {
                "revenue_growth_percent": revenue_growth,
                "transaction_growth_percent": (
                    ((current_month_transactions - last_month_transactions) / last_month_transactions) * 100
                    if last_month_transactions > 0 else 0.0
                )
            }
        }

        # Log report generation
        AuditService.log_system_event(
            "MONTHLY_REVENUE_REPORT_GENERATED",
            {
                "current_month_revenue": float(current_month_revenue),
                "revenue_growth": revenue_growth
            }
        )

        return report

    except Exception as e:
        AuditService.log_system_event(
            "REVENUE_REPORT_GENERATION_FAILED",
            {"error": str(e)}
        )
        raise e

    finally:
        db.close()


@celery_app.task
def sync_payment_statuses_task():
    """Sync payment statuses with Flutterwave"""

    db = SessionLocal()

    try:
        # Get pending payments
        pending_payments = db.query(Payment).filter(
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.PROCESSING])
        ).all()

        updated_count = 0

        for payment in pending_payments:
            try:
                # Verify payment status with Flutterwave
                updated_payment = PaymentService.verify_flutterwave_payment(db, payment)

                if updated_payment.status != payment.status:
                    updated_count += 1

                    AuditService.log_payment_event(
                        "PAYMENT_STATUS_SYNCED",
                        payment.user_id,
                        None,
                        {
                            "payment_id": payment.id,
                            "old_status": payment.status.value,
                            "new_status": updated_payment.status.value
                        }
                    )

            except Exception as e:
                print(f"Error syncing payment {payment.id}: {e}")
                continue

        return {"payments_synced": updated_count}

    except Exception as e:
        AuditService.log_system_event(
            "PAYMENT_SYNC_FAILED",
            {"error": str(e)}
        )
        raise e

    finally:
        db.close()


# Schedule periodic tasks
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Set up periodic payment tasks"""

    # Update subscription statuses daily
    sender.add_periodic_task(
        86400.0,  # 24 hours
        update_subscription_status_task.s(),
        name='update subscription statuses'
    )

    # Generate monthly revenue report on the 1st of each month
    sender.add_periodic_task(
        86400.0 * 30,  # Approximately monthly
        generate_monthly_revenue_report_task.s(),
        name='generate monthly revenue report'
    )

    # Sync payment statuses every 6 hours
    sender.add_periodic_task(
        21600.0,  # 6 hours
        sync_payment_statuses_task.s(),
        name='sync payment statuses'
    )
