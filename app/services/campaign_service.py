"""
Campaign System for Emails and Token Gifting
Comprehensive marketing campaign management with automated workflows
"""

import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session, relationship
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from enum import Enum as PyEnum

from database import get_db, Base
from app.models.user import User
from app.models.campaign import Campaign, CampaignType, CampaignStatus
from app.services.email_service import EmailService
from app.services.token_management_service import TokenManagementService
from app.models.token import TokenType

logger = logging.getLogger(__name__)


# CampaignType and CampaignStatus are imported from app.models.campaign


# Campaign model is imported from app.models.campaign


class CampaignExecution(Base):
    """Campaign execution log and individual recipient tracking"""
    __tablename__ = "campaign_executions"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Execution details
    email_sent = Column(Boolean, default=False)
    email_delivered = Column(Boolean, default=False)
    email_opened = Column(Boolean, default=False)
    email_clicked = Column(Boolean, default=False)
    email_unsubscribed = Column(Boolean, default=False)
    
    # Token gifting
    tokens_gifted = Column(Integer, default=0)
    token_gift_successful = Column(Boolean, default=False)
    token_gift_error = Column(String(500), nullable=True)
    
    # Tracking
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    
    # Error handling
    error_message = Column(String(1000), nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Relationships
    campaign = relationship("Campaign", backref="executions")
    user = relationship("User", backref="campaign_interactions")


class CampaignService:
    """Service for managing marketing campaigns"""

    def __init__(self):
        self.email_service = EmailService()

    @staticmethod
    def create_campaign(
        db: Session,
        admin_user_id: int,
        campaign_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new marketing campaign"""
        try:
            # Validate campaign data
            required_fields = ['name', 'campaign_type']
            for field in required_fields:
                if field not in campaign_data:
                    raise ValueError(f"Missing required field: {field}")

            # Create campaign
            campaign = Campaign(
                name=campaign_data['name'],
                description=campaign_data.get('description'),
                campaign_type=CampaignType(campaign_data['campaign_type']),
                target_audience=campaign_data.get('target_audience'),
                target_user_ids=campaign_data.get('target_user_ids'),
                exclude_user_ids=campaign_data.get('exclude_user_ids'),
                email_subject=campaign_data.get('email_subject'),
                email_template_name=campaign_data.get('email_template_name'),
                email_template_data=campaign_data.get('email_template_data'),
                send_email=campaign_data.get('send_email', False),
                gift_tokens=campaign_data.get('gift_tokens', False),
                token_type=campaign_data.get('token_type'),
                token_amount=campaign_data.get('token_amount'),
                token_message=campaign_data.get('token_message'),
                start_date=datetime.fromisoformat(campaign_data['start_date']) if campaign_data.get('start_date') else None,
                end_date=datetime.fromisoformat(campaign_data['end_date']) if campaign_data.get('end_date') else None,
                send_immediately=campaign_data.get('send_immediately', False),
                recurring=campaign_data.get('recurring', False),
                recurring_interval=campaign_data.get('recurring_interval'),
                max_recipients=campaign_data.get('max_recipients'),
                max_tokens_per_campaign=campaign_data.get('max_tokens_per_campaign'),
                cooldown_hours=campaign_data.get('cooldown_hours', 24),
                created_by=admin_user_id
            )

            db.add(campaign)
            db.commit()
            db.refresh(campaign)

            logger.info(f"Campaign '{campaign.name}' created successfully by user {admin_user_id}")

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
    def get_target_users(db: Session, campaign: Campaign) -> List[User]:
        """Get list of users targeted by campaign"""
        try:
            query = db.query(User).filter(User.status == "active")

            # Apply specific user list if provided
            if campaign.target_user_ids:
                query = query.filter(User.id.in_(campaign.target_user_ids))
                return query.all()

            # Apply audience targeting criteria
            if campaign.target_audience:
                criteria = campaign.target_audience
                
                # User role targeting
                if 'roles' in criteria:
                    query = query.filter(User.role.in_(criteria['roles']))
                
                # Registration date range
                if 'registered_after' in criteria:
                    query = query.filter(User.created_at >= datetime.fromisoformat(criteria['registered_after']))
                if 'registered_before' in criteria:
                    query = query.filter(User.created_at <= datetime.fromisoformat(criteria['registered_before']))
                
                # Email verification status
                if 'email_verified' in criteria:
                    query = query.filter(User.email_verified == criteria['email_verified'])
                
                # Activity-based targeting
                if 'last_login_days_ago' in criteria:
                    cutoff_date = datetime.utcnow() - timedelta(days=criteria['last_login_days_ago'])
                    query = query.filter(User.last_login_at >= cutoff_date)

            # Exclude specific users
            if campaign.exclude_user_ids:
                query = query.filter(~User.id.in_(campaign.exclude_user_ids))

            # Apply recipient limit
            if campaign.max_recipients:
                query = query.limit(campaign.max_recipients)

            return query.all()

        except Exception as e:
            logger.error(f"Failed to get target users: {e}")
            return []

    async def execute_campaign(self, db: Session, campaign_id: int) -> Dict[str, Any]:
        """Execute a campaign (send emails and distribute tokens)"""
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                return {"success": False, "message": "Campaign not found"}

            if campaign.status != CampaignStatus.SCHEDULED:
                return {"success": False, "message": "Campaign is not in scheduled state"}

            # Update campaign status
            campaign.status = CampaignStatus.RUNNING
            campaign.executed_at = datetime.utcnow()
            db.commit()

            # Get target users
            target_users = CampaignService.get_target_users(db, campaign)
            
            if not target_users:
                campaign.status = CampaignStatus.COMPLETED
                campaign.completed_at = datetime.utcnow()
                db.commit()
                return {"success": False, "message": "No target users found"}

            # Execute campaign for each user
            successful_executions = 0
            failed_executions = 0
            total_tokens_distributed = 0

            for user in target_users:
                try:
                    # Create execution record
                    execution = CampaignExecution(
                        campaign_id=campaign_id,
                        user_id=user.id
                    )
                    
                    # Send email if configured
                    if campaign.send_email and campaign.email_subject:
                        email_result = await self._send_campaign_email(campaign, user)
                        execution.email_sent = email_result.get('success', False)
                        if not email_result.get('success'):
                            execution.error_message = email_result.get('error')
                    
                    # Gift tokens if configured
                    if campaign.gift_tokens and campaign.token_amount:
                        token_result = self._gift_campaign_tokens(db, campaign, user)
                        execution.tokens_gifted = token_result.get('amount', 0)
                        execution.token_gift_successful = token_result.get('success', False)
                        if not token_result.get('success'):
                            execution.token_gift_error = token_result.get('error')
                        else:
                            total_tokens_distributed += execution.tokens_gifted
                    
                    execution.sent_at = datetime.utcnow()
                    db.add(execution)
                    successful_executions += 1

                except Exception as e:
                    logger.error(f"Failed to execute campaign for user {user.id}: {e}")
                    execution.error_message = str(e)
                    execution.retry_count += 1
                    db.add(execution)
                    failed_executions += 1

            # Update campaign statistics
            campaign.recipients_count = len(target_users)
            campaign.emails_sent = sum(1 for exec in campaign.executions if exec.email_sent)
            campaign.tokens_distributed = total_tokens_distributed
            campaign.status = CampaignStatus.COMPLETED
            campaign.completed_at = datetime.utcnow()
            
            db.commit()

            logger.info(f"Campaign {campaign_id} executed: {successful_executions} successful, {failed_executions} failed")

            return {
                "success": True,
                "campaign_id": campaign_id,
                "recipients_count": len(target_users),
                "successful_executions": successful_executions,
                "failed_executions": failed_executions,
                "tokens_distributed": total_tokens_distributed,
                "message": "Campaign executed successfully"
            }

        except Exception as e:
            logger.error(f"Failed to execute campaign: {e}")
            # Update campaign status to failed
            try:
                campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
                if campaign:
                    campaign.status = CampaignStatus.CANCELLED
                    db.commit()
            except:
                pass
            
            return {
                "success": False,
                "message": f"Failed to execute campaign: {str(e)}"
            }

    async def _send_campaign_email(self, campaign: Campaign, user: User) -> Dict[str, Any]:
        """Send campaign email to user"""
        try:
            # Prepare template data
            template_data = campaign.email_template_data or {}
            template_data.update({
                'user_name': user.full_name or user.username,
                'user_email': user.email,
                'campaign_name': campaign.name,
                'unsubscribe_url': f"{settings.FRONTEND_URL}/unsubscribe?token={user.id}"
            })

            # Send email using email service
            result = await self.email_service.send_template_email(
                to_email=user.email,
                to_name=user.full_name or user.username,
                subject=campaign.email_subject,
                template_name=campaign.email_template_name or 'campaign',
                template_data=template_data
            )

            return result

        except Exception as e:
            logger.error(f"Failed to send campaign email: {e}")
            return {"success": False, "error": str(e)}

    async def _gift_campaign_tokens(self, db: Session, campaign: Campaign, user: User) -> Dict[str, Any]:
        """Gift tokens to user as part of campaign with notification"""
        try:
            if not campaign.token_amount or campaign.token_amount <= 0:
                return {"success": False, "error": "Invalid token amount"}

            # Determine token type
            token_type = TokenType.DOCUMENT_GENERATION
            if campaign.token_type:
                try:
                    token_type = TokenType(campaign.token_type)
                except ValueError:
                    pass

            # Gift tokens
            success = TokenManagementService.add_tokens(
                db=db,
                user_id=user.id,
                token_type=token_type,
                amount=campaign.token_amount,
                description=campaign.token_message or f"Campaign gift: {campaign.name}",
                reference_id=str(campaign.id),
                reference_type="campaign_gift",
                campaign_id=str(campaign.id)
            )

            if success:
                # Send notification about reward
                await CampaignNotificationService.notify_campaign_reward(
                    user_id=user.id,
                    campaign_id=campaign.id,
                    reward_amount=campaign.token_amount,
                    token_type=token_type
                )

                # Track campaign engagement
                campaign.tokens_distributed += campaign.token_amount
                campaign.recipients_count += 1

                if campaign.token_message:
                    campaign.emails_sent += 1

                db.commit()

                return {
                    "success": True,
                    "amount": campaign.token_amount,
                    "token_type": token_type.value
                }
            else:
                return {"success": False, "error": "Failed to add tokens"}

        except Exception as e:
            logger.error(f"Failed to gift campaign tokens: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def schedule_campaign(db: Session, campaign_id: int) -> Dict[str, Any]:
        """Schedule campaign for execution"""
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                return {"success": False, "message": "Campaign not found"}

            if campaign.status != CampaignStatus.DRAFT:
                return {"success": False, "message": "Only draft campaigns can be scheduled"}

            # Validate campaign configuration
            if campaign.send_email and not campaign.email_subject:
                return {"success": False, "message": "Email subject required for email campaigns"}

            if campaign.gift_tokens and not campaign.token_amount:
                return {"success": False, "message": "Token amount required for token campaigns"}

            # Schedule campaign
            campaign.status = CampaignStatus.SCHEDULED
            if campaign.send_immediately:
                campaign.start_date = datetime.utcnow()
            
            db.commit()

            return {
                "success": True,
                "message": "Campaign scheduled successfully",
                "scheduled_for": campaign.start_date.isoformat() if campaign.start_date else "immediate"
            }

        except Exception as e:
            logger.error(f"Failed to schedule campaign: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}

    @staticmethod
    def get_campaign_analytics(db: Session, campaign_id: int) -> Dict[str, Any]:
        """Get comprehensive campaign analytics"""
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                return {"success": False, "message": "Campaign not found"}

            # Get execution statistics
            executions = db.query(CampaignExecution).filter(
                CampaignExecution.campaign_id == campaign_id
            ).all()

            email_stats = {
                "sent": sum(1 for e in executions if e.email_sent),
                "delivered": sum(1 for e in executions if e.email_delivered),
                "opened": sum(1 for e in executions if e.email_opened),
                "clicked": sum(1 for e in executions if e.email_clicked),
                "unsubscribed": sum(1 for e in executions if e.email_unsubscribed)
            }

            token_stats = {
                "total_gifted": sum(e.tokens_gifted for e in executions),
                "successful_gifts": sum(1 for e in executions if e.token_gift_successful),
                "failed_gifts": sum(1 for e in executions if not e.token_gift_successful and e.tokens_gifted > 0)
            }

            # Calculate rates
            open_rate = (email_stats["opened"] / email_stats["sent"] * 100) if email_stats["sent"] > 0 else 0
            click_rate = (email_stats["clicked"] / email_stats["sent"] * 100) if email_stats["sent"] > 0 else 0
            
            return {
                "success": True,
                "campaign": {
                    "id": campaign.id,
                    "name": campaign.name,
                    "type": campaign.campaign_type.value,
                    "status": campaign.status.value,
                    "created_at": campaign.created_at.isoformat(),
                    "executed_at": campaign.executed_at.isoformat() if campaign.executed_at else None,
                    "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None
                },
                "statistics": {
                    "recipients_count": campaign.recipients_count,
                    "email_stats": email_stats,
                    "token_stats": token_stats,
                    "performance": {
                        "open_rate": round(open_rate, 2),
                        "click_rate": round(click_rate, 2),
                        "token_success_rate": round(
                            (token_stats["successful_gifts"] / len(executions) * 100) if executions else 0, 2
                        )
                    }
                }
            }

        except Exception as e:
            logger.error(f"Failed to get campaign analytics: {e}")
            return {"success": False, "message": str(e)}


# Background task for executing scheduled campaigns
class CampaignScheduler:
    """Background scheduler for campaign execution"""

    @staticmethod
    def check_and_execute_scheduled_campaigns():
        """Check for scheduled campaigns and execute them"""
        try:
            db = next(get_db())
            campaign_service = CampaignService()
            
            # Find campaigns that should be executed now
            now = datetime.utcnow()
            scheduled_campaigns = db.query(Campaign).filter(
                Campaign.status == CampaignStatus.SCHEDULED,
                Campaign.start_date <= now
            ).all()

            for campaign in scheduled_campaigns:
                try:
                    logger.info(f"Executing scheduled campaign: {campaign.name}")
                    asyncio.create_task(
                        campaign_service.execute_campaign(db, campaign.id)
                    )
                except Exception as e:
                    logger.error(f"Failed to execute scheduled campaign {campaign.id}: {e}")

        except Exception as e:
            logger.error(f"Campaign scheduler error: {e}")
        finally:
            try:
                db.close()
            except:
                pass