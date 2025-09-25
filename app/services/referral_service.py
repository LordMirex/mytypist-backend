"""Enhanced referral system service"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.models.referral import ReferralProgram, ReferralTracking
from app.models.token import TokenType
from app.services.token_management_service import TokenManagementService
import secrets
import string
import logging

logger = logging.getLogger(__name__)


class ReferralService:
    """Service for managing referral programs and processing referrals"""

    @staticmethod
    def create_referral_program(
        db: Session,
        admin_user_id: int,
        program_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new referral program"""
        try:
            program = ReferralProgram(
                name=program_data["name"],
                description=program_data.get("description"),
                program_code=program_data["program_code"],
                referrer_token_amount=program_data["referrer_token_amount"],
                referee_token_amount=program_data["referee_token_amount"],
                bonus_multiplier=program_data.get("bonus_multiplier", 1.0),
                max_referrals_per_user=program_data.get("max_referrals_per_user"),
                max_total_referrals=program_data.get("max_total_referrals"),
                max_total_rewards=program_data.get("max_total_rewards"),
                min_referrer_age_days=program_data.get("min_referrer_age_days", 0),
                referrer_requires_email=program_data.get("referrer_requires_email", True),
                referrer_requires_purchase=program_data.get("referrer_requires_purchase", False),
                starts_at=datetime.fromisoformat(program_data["starts_at"]),
                ends_at=datetime.fromisoformat(program_data["ends_at"]),
                created_by=admin_user_id,
            )
            
            db.add(program)
            db.commit()
            db.refresh(program)
            
            return {
                "success": True,
                "program_id": program.id,
                "message": "Referral program created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create referral program: {e}")
            db.rollback()
            return {
                "success": False,
                "message": f"Failed to create referral program: {str(e)}"
            }

    @staticmethod
    async def process_referral(
        db: Session,
        referral_code: str,
        new_user_id: int,
        referral_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a referral when a new user signs up"""
        try:
            # Find existing referral tracking
            tracking = db.query(ReferralTracking).filter(
                and_(
                    ReferralTracking.referral_code == referral_code,
                    ReferralTracking.status == "pending"
                )
            ).first()

            if not tracking:
                return {
                    "success": False,
                    "message": "Invalid or expired referral code"
                }

            # Get referral program
            program = tracking.program
            if not program.is_active:
                return {
                    "success": False,
                    "message": "Referral program is no longer active"
                }

            # Check program limits
            if program.max_total_referrals and program.total_referrals >= program.max_total_referrals:
                return {
                    "success": False,
                    "message": "Referral program has reached maximum referrals"
                }

            # Update tracking
            tracking.referee_id = new_user_id
            tracking.status = "signed_up"
            tracking.sign_up_date = datetime.utcnow()
            if referral_data:
                tracking.metadata = referral_data

            # Calculate rewards
            referrer_reward = int(program.referrer_token_amount * program.bonus_multiplier)
            referee_reward = int(program.referee_token_amount * program.bonus_multiplier)

            # Award tokens to referrer
            referrer_success = TokenManagementService.add_tokens(
                db=db,
                user_id=tracking.referrer_id,
                token_type=TokenType.REFERRAL_BONUS,
                amount=referrer_reward,
                description=f"Referral reward for inviting user {new_user_id}",
                reference_id=str(tracking.id),
                reference_type="referral_reward"
            )

            # Award tokens to new user
            referee_success = TokenManagementService.add_tokens(
                db=db,
                user_id=new_user_id,
                token_type=TokenType.REFERRAL_BONUS,
                amount=referee_reward,
                description=f"Welcome bonus for joining through referral",
                reference_id=str(tracking.id),
                reference_type="referral_welcome"
            )

            # Validate that referee has made a purchase or created a document
            from app.services.user_activity_service import UserActivityService
            has_valid_activity = await UserActivityService.validate_user_activity(
                db=db,
                user_id=new_user_id,
                activity_types=["token_purchase", "document_creation"]
            )
            
            if not has_valid_activity:
                return {
                    "success": False,
                    "message": "Referee must purchase tokens or create a document to complete referral"
                }

            if referrer_success and referee_success:
                # Update tracking and program stats
                tracking.status = "completed"
                tracking.completion_date = datetime.utcnow()
                tracking.referrer_reward = referrer_reward
                tracking.referee_reward = referee_reward
                tracking.referee_ip = ip_address

                # Check for suspicious activity
                from app.services.fraud_detection_service import FraudDetectionService
                is_suspicious = await FraudDetectionService.check_referral(
                    db=db,
                    tracking=tracking,
                    program=program
                )
                tracking.is_suspicious = is_suspicious
                
                program.total_referrals += 1
                program.total_rewards_given += (referrer_reward + referee_reward)
                
                # Update conversion metrics (async in production)
                ReferralService._update_program_metrics(db, program.id)
                
                db.commit()
                
                return {
                    "success": True,
                    "referrer_reward": referrer_reward,
                    "referee_reward": referee_reward,
                    "message": "Referral rewards processed successfully"
                }
            else:
                db.rollback()
                return {
                    "success": False,
                    "message": "Failed to process referral rewards"
                }

        except Exception as e:
            logger.error(f"Failed to process referral: {e}")
            db.rollback()
            return {
                "success": False,
                "message": f"Failed to process referral: {str(e)}"
            }

    @staticmethod
    def create_referral_link(
        db: Session,
        user_id: int,
        program_code: str,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new referral link for a user"""
        try:
            # Get active referral program
            program = db.query(ReferralProgram).filter(
                and_(
                    ReferralProgram.program_code == program_code,
                    ReferralProgram.is_active == True,
                    ReferralProgram.starts_at <= datetime.utcnow(),
                    ReferralProgram.ends_at >= datetime.utcnow()
                )
            ).first()

            if not program:
                return {
                    "success": False,
                    "message": "Invalid or inactive referral program"
                }

            # Check user eligibility
            if program.min_referrer_age_days > 0:
                # Implementation: Check user account age
                pass

            # Check referral limits
            if program.max_referrals_per_user:
                user_referrals = db.query(ReferralTracking).filter(
                    ReferralTracking.referrer_id == user_id,
                    ReferralTracking.program_id == program.id
                ).count()

                if user_referrals >= program.max_referrals_per_user:
                    return {
                        "success": False,
                        "message": "Maximum referrals reached for this program"
                    }

            # Generate unique referral code
            referral_code = ReferralService._generate_referral_code()
            while db.query(ReferralTracking).filter(
                ReferralTracking.referral_code == referral_code
            ).first():
                referral_code = ReferralService._generate_referral_code()

            # Create tracking record
            tracking = ReferralTracking(
                program_id=program.id,
                referrer_id=user_id,
                referral_code=referral_code,
                source=source,
                metadata=metadata,
                referrer_ip=ip_address
            )

            db.add(tracking)
            db.commit()
            db.refresh(tracking)

            return {
                "success": True,
                "referral_code": referral_code,
                "rewards": {
                    "referrer": program.referrer_token_amount,
                    "referee": program.referee_token_amount
                },
                "message": "Referral link created successfully"
            }

        except Exception as e:
            logger.error(f"Failed to create referral link: {e}")
            db.rollback()
            return {
                "success": False,
                "message": f"Failed to create referral link: {str(e)}"
            }

    @staticmethod
    def get_user_referrals(
        db: Session,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get user's referral history"""
        try:
            query = db.query(ReferralTracking).filter(
                ReferralTracking.referrer_id == user_id
            )

            if status:
                query = query.filter(ReferralTracking.status == status)

            total = query.count()
            referrals = query.order_by(ReferralTracking.created_at.desc())\
                            .offset(offset)\
                            .limit(limit)\
                            .all()

            return {
                "success": True,
                "total": total,
                "referrals": [
                    {
                        "id": ref.id,
                        "code": ref.referral_code,
                        "status": ref.status,
                        "created_at": ref.created_at.isoformat(),
                        "signed_up": ref.sign_up_date.isoformat() if ref.sign_up_date else None,
                        "completed": ref.completion_date.isoformat() if ref.completion_date else None,
                        "rewards": {
                            "referrer": ref.referrer_reward,
                            "referee": ref.referee_reward
                        } if ref.status == "completed" else None
                    } for ref in referrals
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get user referrals: {e}")
            return {
                "success": False,
                "message": f"Failed to get referrals: {str(e)}"
            }

    @staticmethod
    def get_program_analytics(
        db: Session,
        program_id: int
    ) -> Dict[str, Any]:
        """Get analytics for a referral program"""
        try:
            program = db.query(ReferralProgram).filter(
                ReferralProgram.id == program_id
            ).first()

            if not program:
                return {
                    "success": False,
                    "message": "Program not found"
                }

            # Get detailed analytics
            total_referrals = program.total_referrals
            total_rewards = program.total_rewards_given
            
            conversion_rate = program.conversion_rate
            retention_rate = program.retention_rate
            roi = program.roi

            # Get recent activity
            recent_referrals = db.query(ReferralTracking)\
                .filter(ReferralTracking.program_id == program_id)\
                .order_by(ReferralTracking.created_at.desc())\
                .limit(10)\
                .all()

            return {
                "success": True,
                "program": {
                    "id": program.id,
                    "name": program.name,
                    "active": program.is_active,
                    "start_date": program.starts_at.isoformat(),
                    "end_date": program.ends_at.isoformat()
                },
                "metrics": {
                    "total_referrals": total_referrals,
                    "total_rewards": total_rewards,
                    "conversion_rate": conversion_rate,
                    "retention_rate": retention_rate,
                    "roi": roi
                },
                "recent_activity": [
                    {
                        "id": ref.id,
                        "status": ref.status,
                        "created_at": ref.created_at.isoformat(),
                        "completed_at": ref.completion_date.isoformat() if ref.completion_date else None
                    } for ref in recent_referrals
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get program analytics: {e}")
            return {
                "success": False,
                "message": f"Failed to get analytics: {str(e)}"
            }

    @staticmethod
    def _generate_referral_code(length: int = 8) -> str:
        """Generate unique referral code"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))

    @staticmethod
    def _update_program_metrics(db: Session, program_id: int):
        """Update program analytics metrics"""
        try:
            program = db.query(ReferralProgram).filter(
                ReferralProgram.id == program_id
            ).first()

            if not program:
                return

            # Calculate conversion rate
            total_referrals = db.query(ReferralTracking)\
                .filter(ReferralTracking.program_id == program_id)\
                .count()

            completed_referrals = db.query(ReferralTracking)\
                .filter(
                    ReferralTracking.program_id == program_id,
                    ReferralTracking.status == "completed"
                )\
                .count()

            if total_referrals > 0:
                program.conversion_rate = (completed_referrals / total_referrals) * 100

            # Calculate retention rate (simplified)
            referred_users = db.query(ReferralTracking)\
                .filter(
                    ReferralTracking.program_id == program_id,
                    ReferralTracking.status == "completed",
                    ReferralTracking.completion_date <= datetime.utcnow() - timedelta(days=30)
                )\
                .count()

            active_referred_users = 0  # Implementation: Count active referred users
            if referred_users > 0:
                program.retention_rate = (active_referred_users / referred_users) * 100

            # Calculate ROI
            total_rewards = program.total_rewards_given
            total_revenue = 0  # Implementation: Calculate revenue from referred users
            if total_rewards > 0:
                program.roi = ((total_revenue - total_rewards) / total_rewards) * 100

            db.commit()

        except Exception as e:
            logger.error(f"Failed to update program metrics: {e}")
            db.rollback()