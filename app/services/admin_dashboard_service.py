"""
Comprehensive Admin Dashboard Service
Handles all statistics, analytics, and administrative functions
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, func, desc, and_, or_
from database import Base
from app.models.user import User
from app.models.template import Template
from app.models.document import Document
from app.models.payment import Payment
from app.models.analytics.visit import PageVisit, DocumentVisit, LandingVisit

logger = logging.getLogger(__name__)


class RetentionMetrics:
    """Data class for retention metrics"""
    def __init__(self):
        self.daily = {}  # Daily retention rates
        self.weekly = {}  # Weekly retention rates
        self.monthly = {}  # Monthly retention rates
        self.cohort_analysis = {}  # Cohort-based retention


class AdminDashboardService:
    """Service for admin dashboard analytics and management"""

    # Performance thresholds
    PERFORMANCE_THRESHOLDS = {
        'response_time': {
            'critical': 1000,  # ms
            'warning': 500,    # ms
            'target': 200      # ms
        },
        'error_rate': {
            'critical': 1.0,   # 1%
            'warning': 0.5,    # 0.5%
            'target': 0.1      # 0.1%
        },
        'cpu_usage': {
            'critical': 90,    # 90%
            'warning': 75,     # 75%
            'target': 50       # 50%
        },
        'memory_usage': {
            'critical': 90,    # 90%
            'warning': 75,     # 75%
            'target': 50       # 50%
        }
    }

    # Risk scoring thresholds
    CHURN_RISK_THRESHOLDS = {
        'high': 0.7,      # 70%+ chance of churning
        'medium': 0.4,    # 40-70% chance of churning
        'low': 0.2        # 20-40% chance of churning
    }

    # Feature weights for recommendations
    RECOMMENDATION_WEIGHTS = {
        'category_affinity': 0.4,
        'user_role_match': 0.3,
        'popularity': 0.2,
        'completion_rate': 0.1
    }

    COHORT_PERIODS = {
        'daily': timedelta(days=1),
        'weekly': timedelta(weeks=1),
        'monthly': timedelta(days=30)
    }

    @staticmethod
    async def get_realtime_stats(db: Session) -> Dict[str, Any]:
        """Get real-time statistics for admin dashboard"""
        try:
            fifteen_mins_ago = datetime.utcnow() - timedelta(minutes=15)
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            # Active users in last 15 minutes from both page and document visits
            page_visitors = set(
                visit.device_fingerprint for visit in
                db.query(PageVisit.device_fingerprint).filter(
                    PageVisit.created_at >= fifteen_mins_ago,
                    PageVisit.device_fingerprint.isnot(None)
                ).all()
            )

            doc_visitors = set(
                visit.device_fingerprint for visit in
                db.query(DocumentVisit.device_fingerprint).filter(
                    DocumentVisit.created_at >= fifteen_mins_ago,
                    DocumentVisit.device_fingerprint.isnot(None)
                ).all()
            )

            active_users = len(page_visitors.union(doc_visitors))

            # Documents being created or viewed now
            active_docs = db.query(DocumentVisit).filter(
                DocumentVisit.created_at >= fifteen_mins_ago,
                DocumentVisit.metadata.op('->>')('action').in_(['create', 'edit'])
            ).count()

            # Current revenue today
            today_revenue = db.query(func.sum(Payment.amount)).filter(
                Payment.status == "completed",
                Payment.created_at >= today_start
            ).scalar() or 0.0

            # Get engagement stats
            avg_session_time = db.query(func.avg(PageVisit.time_on_page_seconds)).filter(
                PageVisit.created_at >= fifteen_mins_ago,
                PageVisit.time_on_page_seconds > 0
            ).scalar() or 0

            bounce_rate = (
                db.query(func.count(1)).filter(
                    PageVisit.created_at >= today_start,
                    PageVisit.bounce.is_(True)
                ).scalar() /
                max(db.query(func.count(1)).filter(
                    PageVisit.created_at >= today_start
                ).scalar(), 1)
            ) * 100

            return {
                "active_users_now": active_users,
                "active_documents": active_docs,
                "revenue_today": today_revenue,
                "avg_session_time": round(avg_session_time, 2),
                "bounce_rate_today": round(bounce_rate, 2),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get realtime stats: {e}")
            raise

    @staticmethod
    async def _get_cohort_conversion(db: Session, user_ids: List[int]) -> Dict[str, float]:
        """Calculate conversion rates for a cohort"""
        total_users = len(user_ids)
        if not total_users:
            return {'trial_to_paid': 0, 'visitor_to_user': 0}

        paid_users = db.query(Payment).filter(
            Payment.user_id.in_(user_ids),
            Payment.status == 'completed'
        ).distinct(Payment.user_id).count()

        active_users = db.query(User).filter(
            User.id.in_(user_ids),
            User.status == 'active'
        ).count()

        return {
            'trial_to_paid': (paid_users / total_users) * 100,
            'visitor_to_user': (active_users / total_users) * 100
        }

    @staticmethod
    async def _get_cohort_retention(
        db: Session,
        user_ids: List[int],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[int, Dict[str, float]]:
        """Calculate detailed retention rates for different periods"""
        retention_rates = {}
        total_users = len(user_ids)

        if not total_users:
            return retention_rates

        current_date = start_date
        day = 0

        while current_date <= end_date:
            # Page visits retention
            page_visitors = set(
                visit.device_fingerprint for visit in
                db.query(PageVisit.device_fingerprint).filter(
                    PageVisit.created_at >= current_date,
                    PageVisit.created_at < current_date + timedelta(days=1),
                    PageVisit.device_fingerprint.isnot(None)
                ).all()
            )

            # Document visits retention
            doc_visitors = set(
                visit.device_fingerprint for visit in
                db.query(DocumentVisit.device_fingerprint).filter(
                    DocumentVisit.created_at >= current_date,
                    DocumentVisit.created_at < current_date + timedelta(days=1),
                    DocumentVisit.device_fingerprint.isnot(None)
                ).all()
            )

            # Calculate retention rates
            total_visitors = len(page_visitors.union(doc_visitors))
            page_retention = (len(page_visitors) / total_users) * 100
            doc_retention = (len(doc_visitors) / total_users) * 100
            overall_retention = (total_visitors / total_users) * 100

            # Store detailed retention metrics
            retention_rates[day] = {
                'overall_retention': round(overall_retention, 2),
                'page_retention': round(page_retention, 2),
                'document_retention': round(doc_retention, 2),
                'active_visitors': total_visitors,
                'date': current_date.date().isoformat()
            }

            current_date += timedelta(days=1)
            day += 1

        return retention_rates

    @staticmethod
    async def _get_cohort_revenue(db: Session, user_ids: List[int]) -> Dict[str, float]:
        """Calculate revenue metrics for a cohort"""
        total_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.user_id.in_(user_ids),
            Payment.status == 'completed'
        ).scalar() or 0.0

        avg_revenue = total_revenue / len(user_ids) if user_ids else 0

        return {
            'total_revenue': total_revenue,
            'average_revenue': avg_revenue
        }

    @staticmethod
    async def _calculate_revenue_metrics(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Calculate comprehensive revenue metrics including MRR, ARR, LTV"""
        # Basic revenue
        total_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.status == "completed",
            Payment.created_at.between(start_time, end_time)
        ).scalar() or 0.0

        # Revenue by product type
        product_revenue = db.query(
            Payment.product_type,
            func.sum(Payment.amount).label('revenue'),
            func.count(Payment.id).label('transactions')
        ).filter(
            Payment.status == "completed",
            Payment.created_at.between(start_time, end_time)
        ).group_by(Payment.product_type).all()

        # Monthly Recurring Revenue (MRR)
        mrr = db.query(func.sum(Subscription.monthly_amount)).filter(
            Subscription.status == 'active'
        ).scalar() or 0.0

        # Annual Recurring Revenue (ARR)
        arr = mrr * 12

        # MRR Growth Rate
        past_mrr = db.query(func.sum(Subscription.monthly_amount)).filter(
            Subscription.status == 'active',
            Subscription.created_at < start_time
        ).scalar() or 0.0
        mrr_growth = ((mrr - past_mrr) / past_mrr * 100) if past_mrr > 0 else 0

        # Churn metrics
        total_customers = db.query(User).filter(
            User.status == 'active'
        ).count()
        churned_customers = db.query(User).filter(
            User.status == 'inactive',
            User.updated_at.between(start_time, end_time)
        ).count()
        churn_rate = (churned_customers / total_customers * 100) if total_customers > 0 else 0

        # Customer value metrics
        customer_value = await AdminDashboardService._calculate_customer_value_metrics(db, start_time, end_time)

        # User acquisition costs and payback period
        acquisition_costs = customer_value.get('acquisition_costs', 0)
        avg_monthly_revenue = mrr / total_customers if total_customers > 0 else 0
        payback_period = acquisition_costs / avg_monthly_revenue if avg_monthly_revenue > 0 else 0

        return {
            'total_revenue': total_revenue,
            'product_revenue': {
                p.product_type: {
                    'revenue': p.revenue,
                    'transactions': p.transactions,
                    'average_transaction': p.revenue / p.transactions if p.transactions else 0
                } for p in product_revenue
            },
            'recurring_revenue': {
                'mrr': mrr,
                'arr': arr,
                'mrr_growth_rate': round(mrr_growth, 2),
                'total_customers': total_customers
            },
            'customer_metrics': {
                'churn_rate': round(churn_rate, 2),
                'payback_period_months': round(payback_period, 2),
                'customer_ltv': customer_value.get('lifetime_value', 0),
                'avg_monthly_revenue_per_user': round(avg_monthly_revenue, 2)
            },
            'customer_value': customer_value
        }

    @staticmethod
    def _calculate_engagement_score(
        page_duration: float,
        doc_duration: float,
        bounce_rate: float,
        doc_interactions: int
    ) -> float:
        """Calculate a comprehensive normalized engagement score from 0-100"""
        # Time engagement (max 30 minutes per session)
        norm_page_duration = min(page_duration / (30 * 60), 1.0)
        norm_doc_duration = min(doc_duration / (30 * 60), 1.0)
        time_engagement = (norm_page_duration + norm_doc_duration) / 2

        # Action engagement
        # Normalize interactions (assume max 100 interactions per period)
        norm_interactions = min(doc_interactions / 100.0, 1.0)

        # Behavioral engagement
        # Bounce rate and session quality
        norm_bounce = 1.0 - (bounce_rate / 100.0)

        # Calculate weighted engagement score
        weights = {
            'time': 0.35,      # Time spent engaging with content
            'actions': 0.35,   # Actions taken (interactions)
            'behavior': 0.30   # Behavioral indicators like bounce rate
        }

        score = (
            (time_engagement * weights['time']) +
            (norm_interactions * weights['actions']) +
            (norm_bounce * weights['behavior'])
        ) * 100

        return round(score, 2)

    @staticmethod
    async def _calculate_subscription_metrics(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Calculate comprehensive subscription and plan metrics"""
        # Basic subscription counts
        active_subs = db.query(Subscription).filter(
            Subscription.status == 'active'
        ).count()

        new_subs = db.query(Subscription).filter(
            Subscription.created_at.between(start_time, end_time)
        ).count()

        churned_subs = db.query(Subscription).filter(
            Subscription.cancelled_at.between(start_time, end_time)
        ).count()

        # Revenue metrics
        mrr = db.query(func.sum(Subscription.monthly_amount)).filter(
            Subscription.status == 'active'
        ).scalar() or 0.0

        # Breakdown by plan type
        plan_metrics = db.query(
            Subscription.plan_type,
            func.count().label('total'),
            func.sum(Subscription.monthly_amount).label('revenue')
        ).filter(
            Subscription.status == 'active'
        ).group_by(Subscription.plan_type).all()

        # Trial metrics
        total_trials = db.query(Subscription).filter(
            Subscription.plan_type == 'trial',
            Subscription.created_at.between(start_time, end_time)
        ).count()

        converted_trials = db.query(Subscription).filter(
            Subscription.plan_type != 'trial',
            Subscription.trial_end_date.between(start_time, end_time)
        ).count()

        trial_conversion = (converted_trials / total_trials * 100) if total_trials > 0 else 0

        # Calculate retention by cohort
        cohort_retention = {}
        cohort_start = start_time
        while cohort_start < end_time:
            cohort_end = cohort_start + timedelta(days=30)
            cohort = db.query(Subscription).filter(
                Subscription.created_at.between(cohort_start, cohort_end),
                Subscription.status == 'active'
            ).count()

            if cohort > 0:
                retained = db.query(Subscription).filter(
                    Subscription.created_at.between(cohort_start, cohort_end),
                    Subscription.status == 'active',
                    Subscription.updated_at >= end_time
                ).count()
                retention_rate = (retained / cohort * 100)
                cohort_retention[cohort_start.strftime('%Y-%m')] = round(retention_rate, 2)

            cohort_start = cohort_end

        return {
            'active_subscriptions': active_subs,
            'new_subscriptions': new_subs,
            'churned_subscriptions': churned_subs,
            'mrr': round(mrr, 2),
            'plans': {
                p.plan_type: {
                    'total': p.total,
                    'revenue': round(p.revenue, 2),
                    'percentage': round(p.total / active_subs * 100, 2) if active_subs > 0 else 0
                } for p in plan_metrics
            },
            'trial_metrics': {
                'total_trials': total_trials,
                'converted_trials': converted_trials,
                'conversion_rate': round(trial_conversion, 2)
            },
            'cohort_retention': cohort_retention,
            'net_revenue_retention': round(
                (active_subs - churned_subs) / active_subs * 100, 2
            ) if active_subs > 0 else 0,
            'quick_ratio': round(
                new_subs / max(churned_subs, 1), 2
            )  # Growth efficiency metric
        }

    @staticmethod
    async def get_system_performance(db: Session, minutes: int = 15) -> Dict[str, Any]:
        """Get comprehensive system performance metrics"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)

        # Get API performance metrics
        api_metrics = db.query(
            func.avg(RequestLog.response_time_ms).label('avg_response_time'),
            func.percentile_cont(0.95).within_group(
                RequestLog.response_time_ms.asc()
            ).label('p95_response_time'),
            func.count().label('total_requests'),
            func.count(case(
                (RequestLog.status_code >= 500, 1)
            )).label('server_errors'),
            func.count(case(
                (RequestLog.status_code >= 400, 1)
            )).label('client_errors')
        ).filter(
            RequestLog.timestamp.between(start_time, end_time)
        ).first()

        total_requests = api_metrics.total_requests or 1
        error_rate = ((api_metrics.server_errors + api_metrics.client_errors) / total_requests) * 100

        # Get database performance metrics
        db_metrics = db.query(
            func.avg(QueryLog.execution_time_ms).label('avg_query_time'),
            func.count().label('total_queries'),
            func.count(case(
                (QueryLog.execution_time_ms > 1000, 1)  # Slow query threshold: 1s
            )).label('slow_queries')
        ).filter(
            QueryLog.timestamp.between(start_time, end_time)
        ).first()

        # Get cache performance
        cache_metrics = db.query(
            func.sum(case((CacheLog.hit == True, 1))).label('hits'),
            func.count().label('total')
        ).filter(
            CacheLog.timestamp.between(start_time, end_time)
        ).first()

        cache_hit_rate = (
            (cache_metrics.hits / cache_metrics.total * 100)
            if cache_metrics.total else 0
        )

        # Get resource utilization (from system metrics table)
        system_metrics = db.query(
            func.avg(SystemMetric.cpu_usage).label('avg_cpu'),
            func.avg(SystemMetric.memory_usage).label('avg_memory'),
            func.avg(SystemMetric.disk_usage).label('avg_disk'),
            func.max(SystemMetric.cpu_usage).label('max_cpu'),
            func.max(SystemMetric.memory_usage).label('max_memory')
        ).filter(
            SystemMetric.timestamp.between(start_time, end_time)
        ).first()

        # Calculate health status
        api_health = (
            'critical' if api_metrics.avg_response_time > AdminDashboardService.PERFORMANCE_THRESHOLDS['response_time']['critical'] or
                        error_rate > AdminDashboardService.PERFORMANCE_THRESHOLDS['error_rate']['critical']
            else 'warning' if api_metrics.avg_response_time > AdminDashboardService.PERFORMANCE_THRESHOLDS['response_time']['warning'] or
                           error_rate > AdminDashboardService.PERFORMANCE_THRESHOLDS['error_rate']['warning']
            else 'healthy'
        )

        system_health = (
            'critical' if system_metrics.avg_cpu > AdminDashboardService.PERFORMANCE_THRESHOLDS['cpu_usage']['critical'] or
                        system_metrics.avg_memory > AdminDashboardService.PERFORMANCE_THRESHOLDS['memory_usage']['critical']
            else 'warning' if system_metrics.avg_cpu > AdminDashboardService.PERFORMANCE_THRESHOLDS['cpu_usage']['warning'] or
                           system_metrics.avg_memory > AdminDashboardService.PERFORMANCE_THRESHOLDS['memory_usage']['warning']
            else 'healthy'
        )

        return {
            'api_performance': {
                'response_times': {
                    'average_ms': round(api_metrics.avg_response_time or 0, 2),
                    'p95_ms': round(api_metrics.p95_response_time or 0, 2)
                },
                'request_metrics': {
                    'total_requests': total_requests,
                    'error_rate': round(error_rate, 2),
                    'success_rate': round(100 - error_rate, 2),
                    'errors': {
                        'server': api_metrics.server_errors,
                        'client': api_metrics.client_errors
                    }
                }
            },
            'database_performance': {
                'query_times': {
                    'average_ms': round(db_metrics.avg_query_time or 0, 2),
                    'slow_queries': db_metrics.slow_queries,
                    'slow_query_rate': round(
                        db_metrics.slow_queries / db_metrics.total_queries * 100 if db_metrics.total_queries else 0,
                        2
                    )
                },
                'throughput': {
                    'queries_per_second': round(
                        db_metrics.total_queries / (minutes * 60), 2
                    )
                }
            },
            'cache_performance': {
                'hit_rate': round(cache_hit_rate, 2),
                'miss_rate': round(100 - cache_hit_rate, 2),
                'total_operations': cache_metrics.total
            },
            'resource_utilization': {
                'cpu': {
                    'current': round(system_metrics.avg_cpu or 0, 2),
                    'max': round(system_metrics.max_cpu or 0, 2)
                },
                'memory': {
                    'current': round(system_metrics.avg_memory or 0, 2),
                    'max': round(system_metrics.max_memory or 0, 2)
                },
                'disk': {
                    'usage_percent': round(system_metrics.avg_disk or 0, 2)
                }
            },
            'health_status': {
                'api': api_health,
                'system': system_health,
                'overall': (
                    'critical' if api_health == 'critical' or system_health == 'critical'
                    else 'warning' if api_health == 'warning' or system_health == 'warning'
                    else 'healthy'
                )
            },
            'timestamp': datetime.utcnow().isoformat()
        }

    @staticmethod
    async def _calculate_business_metrics(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Calculate comprehensive business metrics"""
        # User engagement metrics
        engagement = await AdminDashboardService._calculate_engagement_metrics(db, start_time, end_time)

        # Template usage metrics
        template_metrics = await AdminDashboardService._calculate_template_metrics(db, start_time, end_time)

        # Document metrics
        document_metrics = await AdminDashboardService._calculate_document_metrics(db, start_time, end_time)

        return {
            'engagement': engagement,
            'templates': template_metrics,
            'documents': document_metrics
        }

    @staticmethod
    async def _calculate_engagement_metrics(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Calculate comprehensive user engagement metrics including DAU/MAU ratio and feature adoption"""
        # Daily Active Users (DAU)
        today = datetime.utcnow().date()
        dau = db.query(func.count(distinct(User.id))).filter(
            User.last_login_at >= today
        ).scalar() or 0

        # Monthly Active Users (MAU)
        mau = db.query(func.count(distinct(User.id))).filter(
            User.last_login_at >= today - timedelta(days=30)
        ).scalar() or 0

        # DAU/MAU Ratio (Stickiness)
        stickiness = (dau / mau * 100) if mau > 0 else 0

        # Get unique visitors from both types of visits
        page_visitors = set(
            visit.device_fingerprint for visit in
            db.query(PageVisit.device_fingerprint).filter(
                PageVisit.created_at.between(start_time, end_time),
                PageVisit.device_fingerprint.isnot(None)
            ).all()
        )

        doc_visitors = set(
            visit.device_fingerprint for visit in
            db.query(DocumentVisit.device_fingerprint).filter(
                DocumentVisit.created_at.between(start_time, end_time),
                DocumentVisit.device_fingerprint.isnot(None)
            ).all()
        )

        # Session metrics
        avg_page_duration = db.query(func.avg(PageVisit.time_on_page_seconds)).filter(
            PageVisit.created_at.between(start_time, end_time),
            PageVisit.time_on_page_seconds > 0
        ).scalar() or 0

        avg_doc_duration = db.query(func.avg(DocumentVisit.time_reading)).filter(
            DocumentVisit.created_at.between(start_time, end_time),
            DocumentVisit.time_reading > 0
        ).scalar() or 0

        # Bounce rates
        total_visits = db.query(func.count()).select_from(PageVisit).filter(
            PageVisit.created_at.between(start_time, end_time)
        ).scalar()

        bounced_visits = db.query(func.count()).select_from(PageVisit).filter(
            PageVisit.created_at.between(start_time, end_time),
            PageVisit.bounce.is_(True)
        ).scalar()

        bounce_rate = (bounced_visits / total_visits * 100) if total_visits > 0 else 0

        # Feature adoption rates
        feature_usage = {
            'template_marketplace': db.query(func.count(distinct(User.id))).join(
                Template, Template.user_id == User.id
            ).scalar(),
            'document_creation': db.query(func.count(distinct(User.id))).join(
                Document, Document.user_id == User.id
            ).scalar(),
            'api_usage': db.query(func.count(distinct(User.id))).filter(
                User.api_key.isnot(None)
            ).scalar()
        }

        total_users = db.query(func.count(User.id)).scalar() or 1
        feature_adoption = {
            feature: round(count / total_users * 100, 2)
            for feature, count in feature_usage.items()
        }

        # NPS calculation from feedback
        nps_scores = db.query(
            Feedback.score,
            func.count().label('count')
        ).filter(
            Feedback.created_at.between(start_time, end_time),
            Feedback.type == 'nps'
        ).group_by(Feedback.score).all()

        promoters = sum(row.count for row in nps_scores if row.score >= 9)
        detractors = sum(row.count for row in nps_scores if row.score <= 6)
        total_nps = sum(row.count for row in nps_scores)

        nps_score = (
            (promoters - detractors) / total_nps * 100
        ) if total_nps > 0 else 0

        # User journey analytics
        journey_stages = {
            'signup_complete': db.query(func.count(User.id)).filter(
                User.status != 'pending'
            ).scalar(),
            'template_used': db.query(func.count(distinct(Document.user_id))).scalar(),
            'document_completed': db.query(func.count(distinct(Document.user_id))).filter(
                Document.status == 'completed'
            ).scalar(),
            'subscription_started': db.query(func.count(distinct(Subscription.user_id))).filter(
                Subscription.status == 'active'
            ).scalar()
        }

        journey_conversion = {
            stage: round(count / total_users * 100, 2)
            for stage, count in journey_stages.items()
        }

        return {
            'activity_metrics': {
                'dau': dau,
                'mau': mau,
                'stickiness': round(stickiness, 2),
                'total_visitors': len(page_visitors.union(doc_visitors)),
                'unique_visitors': {
                    'page': len(page_visitors),
                    'document': len(doc_visitors)
                }
            },
            'session_metrics': {
                'average_page_duration': round(avg_page_duration, 2),
                'average_document_duration': round(avg_doc_duration, 2),
                'total_session_time': round(avg_page_duration + avg_doc_duration, 2),
                'bounce_rate': round(bounce_rate, 2)
            },
            'feature_adoption': feature_adoption,
            'nps': {
                'score': round(nps_score, 2),
                'promoters': promoters,
                'detractors': detractors,
                'total_responses': total_nps
            },
            'user_journey': journey_conversion,
            'engagement_score': AdminDashboardService._calculate_engagement_score(
                avg_page_duration, avg_doc_duration, bounce_rate,
                db.query(DocumentVisit).filter(
                    DocumentVisit.created_at.between(start_time, end_time)
                ).count()
            )
        }

    @staticmethod
    async def _calculate_template_metrics(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Calculate comprehensive template usage and performance metrics"""
        # Basic template metrics
        templates_created = db.query(Template).filter(
            Template.created_at.between(start_time, end_time)
        ).count()

        # Template usage and popularity
        template_usage = db.query(
            Template.id,
            Template.name,
            Template.category,
            func.count(Document.id).label('usage_count'),
            func.avg(Document.completion_time_seconds).label('avg_completion_time'),
            func.count(distinct(Document.user_id)).label('unique_users')
        ).outerjoin(Document).filter(
            Document.created_at.between(start_time, end_time)
        ).group_by(Template.id).all()

        # Category performance
        category_metrics = db.query(
            TemplateCategory.name,
            func.count(Document.id).label('usage_count'),
            func.count(distinct(Document.user_id)).label('unique_users'),
            func.avg(Document.completion_time_seconds).label('avg_completion_time')
        ).join(Template).join(Document).filter(
            Document.created_at.between(start_time, end_time)
        ).group_by(TemplateCategory.name).all()

        # Search analytics
        search_patterns = db.query(
            SearchLog.query,
            func.count().label('search_count'),
            func.avg(SearchLog.result_count).label('avg_results'),
            func.sum(case(
                (SearchLog.resulted_in_use == True, 1),
                else_=0
            )).label('successful_searches')
        ).filter(
            SearchLog.created_at.between(start_time, end_time)
        ).group_by(SearchLog.query).all()

        # Template performance metrics
        performance_metrics = db.query(
            Template.id,
            func.count(case(
                (Document.status == 'completed', 1)
            )).label('completions'),
            func.count(case(
                (Document.status == 'abandoned', 1)
            )).label('abandonments'),
            func.avg(Document.user_satisfaction_score).label('avg_satisfaction')
        ).join(Document).group_by(Template.id).all()

        return {
            'summary': {
                'templates_created': templates_created,
                'total_templates': db.query(func.count(Template.id)).scalar(),
                'active_templates': db.query(func.count(Template.id)).filter(
                    Template.status == 'active'
                ).scalar()
            },
            'popular_templates': [
                {
                    'id': t.id,
                    'name': t.name,
                    'category': t.category,
                    'usage_count': t.usage_count,
                    'unique_users': t.unique_users,
                    'avg_completion_time': round(t.avg_completion_time or 0, 2)
                }
                for t in sorted(template_usage, key=lambda x: x.usage_count, reverse=True)[:10]
            ],
            'category_performance': [
                {
                    'category': c.name,
                    'usage_count': c.usage_count,
                    'unique_users': c.unique_users,
                    'avg_completion_time': round(c.avg_completion_time or 0, 2)
                }
                for c in category_metrics
            ],
            'search_analytics': {
                'top_searches': [
                    {
                        'query': s.query,
                        'count': s.search_count,
                        'avg_results': round(s.avg_results or 0, 2),
                        'success_rate': round(
                            s.successful_searches / s.search_count * 100, 2
                        ) if s.search_count > 0 else 0
                    }
                    for s in sorted(search_patterns, key=lambda x: x.search_count, reverse=True)[:10]
                ],
                'zero_result_queries': [
                    s.query for s in search_patterns if s.avg_results == 0
                ]
            },
            'template_performance': {
                str(p.id): {
                    'completion_rate': round(
                        p.completions / (p.completions + p.abandonments) * 100, 2
                    ) if (p.completions + p.abandonments) > 0 else 0,
                    'satisfaction_score': round(p.avg_satisfaction or 0, 2)
                }
                for p in performance_metrics
            }
        }

    @staticmethod
    async def _calculate_document_metrics(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Calculate comprehensive document creation, usage, and performance metrics"""
        # Basic document counts
        total_documents = db.query(Document).filter(
            Document.created_at.between(start_time, end_time)
        ).count()

        completed_documents = db.query(Document).filter(
            Document.created_at.between(start_time, end_time),
            Document.status == 'completed'
        ).count()

        # Document performance metrics
        completion_time_stats = db.query(
            func.avg(Document.completion_time_seconds).label('avg_time'),
            func.min(Document.completion_time_seconds).label('min_time'),
            func.max(Document.completion_time_seconds).label('max_time'),
            func.percentile_cont(0.50).within_group(
                Document.completion_time_seconds.asc()
            ).label('median_time')
        ).filter(
            Document.status == 'completed',
            Document.created_at.between(start_time, end_time)
        ).first()

        # Document status distribution
        status_counts = db.query(
            Document.status,
            func.count().label('count')
        ).filter(
            Document.created_at.between(start_time, end_time)
        ).group_by(Document.status).all()

        # Error analysis
        error_analysis = db.query(
            Document.error_type,
            func.count().label('count'),
            func.array_agg(Document.error_message).label('messages')
        ).filter(
            Document.status == 'error',
            Document.created_at.between(start_time, end_time)
        ).group_by(Document.error_type).all()

        # User satisfaction metrics
        satisfaction_stats = db.query(
            func.avg(Document.user_satisfaction_score).label('avg_score'),
            func.count().label('total_ratings')
        ).filter(
            Document.created_at.between(start_time, end_time),
            Document.user_satisfaction_score.isnot(None)
        ).first()

        # Document revision metrics
        revision_stats = db.query(
            func.avg(Document.revision_count).label('avg_revisions'),
            func.sum(Document.revision_count).label('total_revisions')
        ).filter(
            Document.created_at.between(start_time, end_time)
        ).first()

        # Time savings analysis
        time_savings = db.query(
            func.sum(Document.estimated_time_saved_minutes).label('total_saved'),
            func.avg(Document.estimated_time_saved_minutes).label('avg_saved')
        ).filter(
            Document.created_at.between(start_time, end_time),
            Document.estimated_time_saved_minutes.isnot(None)
        ).first()

        return {
            'volume_metrics': {
                'total_documents': total_documents,
                'completed_documents': completed_documents,
                'completion_rate': round(
                    completed_documents / total_documents * 100, 2
                ) if total_documents > 0 else 0
            },
            'performance_metrics': {
                'avg_completion_time': round(completion_time_stats.avg_time or 0, 2),
                'min_completion_time': round(completion_time_stats.min_time or 0, 2),
                'max_completion_time': round(completion_time_stats.max_time or 0, 2),
                'median_completion_time': round(completion_time_stats.median_time or 0, 2)
            },
            'status_distribution': {
                status.status: {
                    'count': status.count,
                    'percentage': round(status.count / total_documents * 100, 2)
                }
                for status in status_counts
            },
            'error_analysis': [
                {
                    'type': error.error_type,
                    'count': error.count,
                    'sample_messages': error.messages[:5]  # Show up to 5 sample messages
                }
                for error in error_analysis
            ],
            'user_satisfaction': {
                'average_score': round(satisfaction_stats.avg_score or 0, 2),
                'total_ratings': satisfaction_stats.total_ratings,
                'response_rate': round(
                    satisfaction_stats.total_ratings / total_documents * 100, 2
                ) if total_documents > 0 else 0
            },
            'revision_metrics': {
                'average_revisions': round(revision_stats.avg_revisions or 0, 2),
                'total_revisions': revision_stats.total_revisions or 0
            },
            'time_savings': {
                'total_hours_saved': round((time_savings.total_saved or 0) / 60, 2),
                'average_minutes_saved': round(time_savings.avg_saved or 0, 2)
            }
        }

    @staticmethod
    async def _calculate_customer_value_metrics(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Calculate comprehensive customer value and revenue metrics"""
        # Get paying users
        paying_users = db.query(Payment.user_id).distinct().filter(
            Payment.status == 'completed'
        ).count()

        # Total revenue from completed payments
        total_revenue = db.query(func.sum(Payment.amount)).filter(
            Payment.status == 'completed'
        ).scalar() or 0.0

        # Average revenue per user
        arpu = total_revenue / paying_users if paying_users else 0

        # Customer acquisition costs (marketing + onboarding costs)
        # TODO: Replace with actual marketing cost tracking when implemented
        estimated_acquisition_cost = 5000  # Placeholder cost in currency units

        # Calculate average customer lifetime in months
        customer_lifetimes = db.query(
            (func.julianday(User.updated_at) - func.julianday(User.created_at)) / 30
        ).filter(
            User.status == 'inactive'
        ).all()
        avg_lifetime_months = (
            sum(lifetime[0] for lifetime in customer_lifetimes) / len(customer_lifetimes)
            if customer_lifetimes else 12  # Default to 12 months if no churn data
        )

        # Calculate LTV using average customer lifetime and ARPU
        customer_ltv = arpu * avg_lifetime_months

        # Get upgrade rates
        total_upgrades = db.query(func.count()).filter(
            SubscriptionChange.change_type == 'upgrade',
            SubscriptionChange.created_at.between(start_time, end_time)
        ).scalar() or 0

        upgrade_rate = (total_upgrades / paying_users * 100) if paying_users else 0

        return {
            'lifetime_value': round(customer_ltv, 2),
            'average_customer_value': round(arpu, 2),
            'customer_count': paying_users,
            'revenue_per_user': round(arpu, 2),
            'acquisition_costs': estimated_acquisition_cost,
            'avg_lifetime_months': round(avg_lifetime_months, 2),
            'upgrade_rate': round(upgrade_rate, 2)
        }

    @staticmethod
    async def calculate_churn_risk(db: Session, user_id: int) -> Dict[str, Any]:
        """Calculate churn risk score and factors for a user"""
        # Get user's activity data
        user = db.query(User).get(user_id)
        if not user:
            return {"error": "User not found"}

        # Calculate days since last activity
        days_inactive = (datetime.utcnow() - user.last_login_at).days

        # Get recent engagement metrics
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        engagement = db.query(
            func.count(PageVisit.id).label('page_visits'),
            func.count(DocumentVisit.id).label('doc_visits'),
            func.avg(PageVisit.time_on_page_seconds).label('avg_session_time')
        ).filter(
            or_(
                PageVisit.user_id == user_id,
                DocumentVisit.user_id == user_id
            ),
            or_(
                PageVisit.created_at >= thirty_days_ago,
                DocumentVisit.created_at >= thirty_days_ago
            )
        ).first()

        # Get subscription status
        subscription = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == 'active'
        ).first()

        # Calculate feature usage decline
        recent_feature_usage = await AdminDashboardService._calculate_feature_usage(
            db, user_id, days=30
        )
        previous_feature_usage = await AdminDashboardService._calculate_feature_usage(
            db, user_id, days=60, offset=30
        )

        feature_decline = (
            (previous_feature_usage - recent_feature_usage) / previous_feature_usage
            if previous_feature_usage > 0 else 0
        )

        # Calculate risk factors
        risk_factors = {
            'inactivity': min(days_inactive / 30, 1.0),
            'low_engagement': 1.0 - min(
                (engagement.page_visits + engagement.doc_visits) / 100, 1.0
            ),
            'session_time': 1.0 - min(
                (engagement.avg_session_time or 0) / 3600, 1.0
            ),
            'feature_decline': feature_decline
        }

        # Calculate weighted risk score
        weights = {
            'inactivity': 0.4,
            'low_engagement': 0.3,
            'session_time': 0.2,
            'feature_decline': 0.1
        }

        risk_score = sum(
            score * weights[factor]
            for factor, score in risk_factors.items()
        )

        # Determine risk level
        risk_level = (
            'high' if risk_score >= AdminDashboardService.CHURN_RISK_THRESHOLDS['high']
            else 'medium' if risk_score >= AdminDashboardService.CHURN_RISK_THRESHOLDS['medium']
            else 'low' if risk_score >= AdminDashboardService.CHURN_RISK_THRESHOLDS['low']
            else 'minimal'
        )

        return {
            'risk_score': round(risk_score * 100, 2),
            'risk_level': risk_level,
            'risk_factors': {
                k: round(v * 100, 2) for k, v in risk_factors.items()
            },
            'recommendations': [
                {
                    'type': 'feature_adoption',
                    'message': 'Increase engagement through key feature adoption',
                    'features': [f for f in ['template_marketplace', 'api_usage', 'team_collaboration']
                               if f not in user.features_used]
                } if risk_factors['low_engagement'] > 0.5 else None,
                {
                    'type': 'reactivation',
                    'message': 'Send reactivation email with personalized content',
                    'last_login': user.last_login_at.isoformat()
                } if risk_factors['inactivity'] > 0.7 else None,
                {
                    'type': 'support_outreach',
                    'message': 'Initiate proactive support outreach',
                    'reason': 'Declining feature usage trend'
                } if risk_factors['feature_decline'] > 0.3 else None
            ]
        }

    @staticmethod
    async def get_template_recommendations(
        db: Session,
        user_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get personalized template recommendations for a user"""
        # Get user's historical template usage
        user_templates = db.query(
            Document.template_id,
            func.count().label('usage_count')
        ).filter(
            Document.user_id == user_id
        ).group_by(Document.template_id).all()

        # Get user's role and industry
        user = db.query(User).get(user_id)
        if not user:
            return []

        # Calculate category affinity
        category_usage = db.query(
            Template.category,
            func.count().label('usage_count')
        ).join(Document).filter(
            Document.user_id == user_id
        ).group_by(Template.category).all()

        preferred_categories = {
            cat.category: cat.usage_count
            for cat in category_usage
        }

        # Get global template popularity
        popular_templates = db.query(
            Template,
            func.count(Document.id).label('usage_count'),
            func.avg(Document.user_satisfaction_score).label('satisfaction'),
            func.count(distinct(Document.user_id)).label('unique_users')
        ).join(Document).group_by(Template.id).all()

        # Calculate recommendation scores
        recommendations = []
        for template in popular_templates:
            # Skip templates already used by user
            if template.Template.id in [t.template_id for t in user_templates]:
                continue

            # Category affinity score
            category_score = (
                preferred_categories.get(template.Template.category, 0) /
                max(preferred_categories.values()) if preferred_categories else 0
            )

            # Role match score
            role_score = 1.0 if template.Template.target_role == user.role else 0.5

            # Popularity score
            popularity_score = template.usage_count / max(t.usage_count for t in popular_templates)

            # Completion rate score
            completion_rate = (
                db.query(
                    func.count(case((Document.status == 'completed', 1))) /
                    func.count()
                ).filter(
                    Document.template_id == template.Template.id
                ).scalar() or 0
            )

            # Calculate weighted score
            total_score = (
                category_score * AdminDashboardService.RECOMMENDATION_WEIGHTS['category_affinity'] +
                role_score * AdminDashboardService.RECOMMENDATION_WEIGHTS['user_role_match'] +
                popularity_score * AdminDashboardService.RECOMMENDATION_WEIGHTS['popularity'] +
                completion_rate * AdminDashboardService.RECOMMENDATION_WEIGHTS['completion_rate']
            )

            recommendations.append({
                'template_id': template.Template.id,
                'name': template.Template.name,
                'category': template.Template.category,
                'score': round(total_score * 100, 2),
                'reason': 'Based on your role and document history',
                'metrics': {
                    'usage_count': template.usage_count,
                    'satisfaction_score': round(template.satisfaction or 0, 2),
                    'unique_users': template.unique_users
                }
            })

        # Sort by score and return top N
        return sorted(recommendations, key=lambda x: x['score'], reverse=True)[:limit]

    @staticmethod
    async def _calculate_feature_usage(
        db: Session,
        user_id: int,
        days: int = 30,
        offset: int = 0
    ) -> float:
        """Calculate normalized feature usage score for a time period"""
        end_date = datetime.utcnow() - timedelta(days=offset)
        start_date = end_date - timedelta(days=days)

        # Count different types of feature usage
        feature_usage = db.query(
            func.count(distinct(Document.id)).label('documents'),
            func.count(distinct(Template.id)).label('templates'),
            func.count(distinct(PageVisit.id)).label('pages'),
            func.count(distinct(case((Subscription.id.isnot(None), Subscription.id)))).label('subscriptions')
        ).outerjoin(Document).outerjoin(Template).outerjoin(PageVisit).outerjoin(Subscription).filter(
            or_(
                Document.user_id == user_id,
                Template.user_id == user_id,
                PageVisit.user_id == user_id,
                Subscription.user_id == user_id
            ),
            or_(
                Document.created_at.between(start_date, end_date),
                Template.created_at.between(start_date, end_date),
                PageVisit.created_at.between(start_date, end_date),
                Subscription.created_at.between(start_date, end_date)
            )
        ).first()

        # Normalize usage (assume max 100 interactions per feature type per month)
        normalized_usage = sum(
            min(getattr(feature_usage, feature) / 100, 1.0)
            for feature in ['documents', 'templates', 'pages', 'subscriptions']
        ) / 4  # Average across feature types

        return normalized_usage

    @staticmethod
    async def get_cohort_analysis(db: Session, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get detailed cohort analysis for a specific date range"""
        try:
            cohorts = {}
            current_date = start_date

            while current_date <= end_date:
                # Get users who joined on this date
                new_users = db.query(User).filter(
                    func.date(User.created_at) == current_date.date()
                ).all()

                if new_users:
                    user_ids = [u.id for u in new_users]
                    cohort_metrics = {
                        'size': len(user_ids),
                        'conversion_rate': await AdminDashboardService._get_cohort_conversion(db, user_ids),
                        'retention': await AdminDashboardService._get_cohort_retention(db, user_ids, current_date, end_date),
                        'revenue': await AdminDashboardService._get_cohort_revenue(db, user_ids)
                    }
                    cohorts[current_date.strftime('%Y-%m-%d')] = cohort_metrics

                current_date += timedelta(days=1)

            return cohorts
        except Exception as e:
            logger.error(f"Failed to get cohort analysis: {e}")
            raise

    @staticmethod
    async def calculate_retention_metrics(db: Session, date: datetime) -> RetentionMetrics:
        """Calculate comprehensive retention metrics"""
        retention = RetentionMetrics()
        end_date = date
        start_date = end_date - timedelta(days=90)  # 90 days of history

        # Get all user activity in period
        user_activity = db.query(
            User.id,
            User.created_at,
            PageVisit.created_at.label('visit_date')
        ).join(PageVisit).filter(
            User.created_at.between(start_date, end_date)
        ).all()

        # Calculate retention by periods
        for period_name, period_delta in AdminDashboardService.COHORT_PERIODS.items():
            cohorts = {}
            current_date = start_date

            while current_date <= end_date:
                period_end = current_date + period_delta

                # Get new users in this period
                new_users = set(
                    user.id for user in user_activity
                    if current_date <= user.created_at < period_end
                )

                if new_users:
                    retained_users = {}
                    check_date = period_end
                    period_number = 1

                    # Calculate retention for subsequent periods
                    while check_date <= end_date:
                        active_users = set(
                            user.id for user in user_activity
                            if user.id in new_users and
                            check_date <= user.visit_date < (check_date + period_delta)
                        )

                        retained_users[period_number] = {
                            'count': len(active_users),
                            'percentage': (len(active_users) / len(new_users)) * 100
                        }

                        check_date += period_delta
                        period_number += 1

                    cohorts[current_date.strftime('%Y-%m-%d')] = {
                        'new_users': len(new_users),
                        'retention': retained_users
                    }

                current_date += period_delta

            # Store cohort analysis
            if period_name == 'daily':
                retention.daily = cohorts
            elif period_name == 'weekly':
                retention.weekly = cohorts
            else:
                retention.monthly = cohorts

        return retention

    @staticmethod
    async def get_daily_summary(db: Session, date: datetime) -> Dict[str, Any]:
        """Get or generate daily analytics summary"""
        try:
            # Try to get existing summary
            summary = db.query(AnalyticsSummary).filter(
                func.date(AnalyticsSummary.date) == date.date()
            ).first()

            if summary:
                return json.loads(summary.top_pages) if summary.top_pages else {}

            # Generate new summary
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)

            # User metrics
            new_users = db.query(User).filter(
                User.created_at.between(start_of_day, end_of_day)
            ).count()

            active_users = db.query(PageVisit).filter(
                PageVisit.created_at.between(start_of_day, end_of_day)
            ).distinct(PageVisit.user_id).count()

            # Document metrics
            docs_created = db.query(Document).filter(
                Document.created_at.between(start_of_day, end_of_day)
            ).count()

            # Enhanced Revenue Metrics
            revenue_metrics = await AdminDashboardService._calculate_revenue_metrics(
                db, start_of_day, end_of_day
            )

            # Enhanced Business Metrics
            business_metrics = await AdminDashboardService._calculate_business_metrics(
                db, start_of_day, end_of_day
            )

            # Visit metrics with enhanced tracking
            visit_metrics = await AdminDashboardService._calculate_visit_metrics(
                db, start_of_day, end_of_day
            )

            # Get retention metrics
            retention = await AdminDashboardService.calculate_retention_metrics(db, date)

            # Create summary record
            summary = AnalyticsSummary(
                date=date,
                total_users=db.query(User).count(),
                new_users=new_users,
                active_users=active_users,
                documents_created=docs_created,
                revenue_amount=revenue,
                total_visits=len(visits),
                unique_visitors=len(set(v.session_id for v in visits)),
                avg_visit_duration=sum(v.visit_duration for v in visits) / len(visits) if visits else 0
            )

            db.add(summary)
            await db.commit()
            await db.refresh(summary)

            return {
                "date": date.isoformat(),
                "metrics": {
                    "users": {
                        "total": summary.total_users,
                        "new": summary.new_users,
                        "active": summary.active_users
                    },
                    "documents": {
                        "created": summary.documents_created,
                        "downloaded": summary.documents_downloaded
                    },
                    "revenue": {
                        "total": summary.revenue_amount,
                        "currency": summary.revenue_currency
                    },
                    "visits": {
                        "total": summary.total_visits,
                        "unique": summary.unique_visitors,
                        "avg_duration": summary.avg_visit_duration
                    }
                }
            }
        except Exception as e:
            logger.error(f"Failed to generate daily summary: {e}")
            raise


# PageVisit model is imported from app.models.analytics.visit


class AnalyticsSummary(Base):
    """Daily analytics summary for quick dashboard access"""
    __tablename__ = "analytics_summaries"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, index=True)

    # User metrics
    total_users = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    active_users = Column(Integer, default=0)

    # Document metrics
    documents_created = Column(Integer, default=0)
    documents_downloaded = Column(Integer, default=0)
    template_submissions = Column(Integer, default=0)

    # Revenue metrics
    revenue_amount = Column(Float, default=0.0)
    revenue_currency = Column(String(3), default="NGN")
    subscription_revenue = Column(Float, default=0.0)
    pay_as_you_go_revenue = Column(Float, default=0.0)

    # Visit metrics
    total_visits = Column(Integer, default=0)
    unique_visitors = Column(Integer, default=0)
    avg_visit_duration = Column(Float, default=0.0)  # seconds
    bounce_rate = Column(Float, default=0.0)  # percentage

    # Most visited pages (JSON array of {path, count})
    top_pages = Column(Text, nullable=True)

    # Performance metrics
    avg_response_time = Column(Float, default=0.0)  # milliseconds
    error_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)


class DocumentShare(Base):
    """Document sharing with time-limited access"""
    __tablename__ = "document_shares"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False, index=True)
    shared_by = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    share_token = Column(String(100), unique=True, nullable=False, index=True)
    share_password = Column(String(255), nullable=True)  # Auto-generated password

    # Access control
    expires_at = Column(DateTime, nullable=False, index=True)
    max_views = Column(Integer, default=None)  # Optional view limit
    current_views = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, nullable=True)
    access_log = Column(Text, nullable=True)  # JSON log of access attempts


class AdminDashboardService:
    """Comprehensive admin dashboard with all statistics and management functions"""

    @staticmethod
    def get_comprehensive_dashboard_stats(db: Session) -> Dict[str, Any]:
        """
        Get all dashboard statistics including earnings, customers, visits, and analytics
        """
        try:
            # Time ranges for analytics
            today = datetime.utcnow().date()
            yesterday = today - timedelta(days=1)
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)

            # User Statistics
            total_users = db.query(User).count()
            new_users_today = db.query(User).filter(
                func.date(User.created_at) == today
            ).count()
            new_users_week = db.query(User).filter(
                func.date(User.created_at) >= week_ago
            ).count()
            new_users_month = db.query(User).filter(
                func.date(User.created_at) >= month_ago
            ).count()

            # Active users (visited in last 7 days)
            active_users = db.query(PageVisit).filter(
                PageVisit.created_at >= datetime.utcnow() - timedelta(days=7),
                PageVisit.user_id.isnot(None)
            ).distinct(PageVisit.user_id).count()

            # Document Statistics
            total_documents = db.query(Document).count()
            documents_today = db.query(Document).filter(
                func.date(Document.created_at) == today
            ).count()
            documents_week = db.query(Document).filter(
                func.date(Document.created_at) >= week_ago
            ).count()
            documents_month = db.query(Document).filter(
                func.date(Document.created_at) >= month_ago
            ).count()

            # Template Statistics
            total_templates = db.query(Template).count()
            active_templates = db.query(Template).filter(
                Template.is_active == True
            ).count()

            # Payment/Revenue Statistics
            total_revenue = db.query(func.sum(Payment.amount)).filter(
                Payment.status == "completed"
            ).scalar() or 0

            revenue_today = db.query(func.sum(Payment.amount)).filter(
                Payment.status == "completed",
                func.date(Payment.created_at) == today
            ).scalar() or 0

            revenue_week = db.query(func.sum(Payment.amount)).filter(
                Payment.status == "completed",
                func.date(Payment.created_at) >= week_ago
            ).scalar() or 0

            revenue_month = db.query(func.sum(Payment.amount)).filter(
                Payment.status == "completed",
                func.date(Payment.created_at) >= month_ago
            ).scalar() or 0

            # Page Visit Statistics
            total_visits = db.query(PageVisit).count()
            visits_today = db.query(PageVisit).filter(
                func.date(PageVisit.created_at) == today
            ).count()
            visits_week = db.query(PageVisit).filter(
                func.date(PageVisit.created_at) >= week_ago
            ).count()

            # Average visit duration
            avg_visit_duration = db.query(func.avg(PageVisit.visit_duration)).filter(
                PageVisit.visit_duration > 0
            ).scalar() or 0

            # Most visited pages
            popular_pages = db.query(
                PageVisit.page_path,
                func.count(PageVisit.id).label('visit_count')
            ).group_by(PageVisit.page_path).order_by(
                desc('visit_count')
            ).limit(10).all()

            # User role distribution
            role_distribution = db.query(
                User.role,
                func.count(User.id).label('count')
            ).group_by(User.role).all()

            # Recent activity
            recent_users = db.query(User).order_by(desc(User.created_at)).limit(5).all()
            recent_documents = db.query(Document).order_by(desc(Document.created_at)).limit(5).all()
            recent_payments = db.query(Payment).order_by(desc(Payment.created_at)).limit(5).all()

            # Device and browser analytics
            device_stats = db.query(
                PageVisit.device_type,
                func.count(PageVisit.id).label('count')
            ).filter(
                PageVisit.device_type.isnot(None)
            ).group_by(PageVisit.device_type).all()

            browser_stats = db.query(
                PageVisit.browser,
                func.count(PageVisit.id).label('count')
            ).filter(
                PageVisit.browser.isnot(None)
            ).group_by(PageVisit.browser).limit(10).all()

            return {
                "success": True,
                "timestamp": datetime.utcnow().isoformat(),
                "overview": {
                    "total_users": total_users,
                    "total_documents": total_documents,
                    "total_templates": total_templates,
                    "total_revenue": float(total_revenue),
                    "total_visits": total_visits,
                    "active_users": active_users,
                    "active_templates": active_templates
                },
                "growth": {
                    "users": {
                        "today": new_users_today,
                        "week": new_users_week,
                        "month": new_users_month
                    },
                    "documents": {
                        "today": documents_today,
                        "week": documents_week,
                        "month": documents_month
                    },
                    "revenue": {
                        "today": float(revenue_today),
                        "week": float(revenue_week),
                        "month": float(revenue_month)
                    },
                    "visits": {
                        "today": visits_today,
                        "week": visits_week,
                        "average_duration": float(avg_visit_duration)
                    }
                },
                "analytics": {
                    "popular_pages": [
                        {"page": page, "visits": count}
                        for page, count in popular_pages
                    ],
                    "user_roles": [
                        {"role": role, "count": count}
                        for role, count in role_distribution
                    ],
                    "devices": [
                        {"device": device, "count": count}
                        for device, count in device_stats
                    ],
                    "browsers": [
                        {"browser": browser, "count": count}
                        for browser, count in browser_stats
                    ]
                },
                "recent_activity": {
                    "users": [
                        {
                            "id": user.id,
                            "email": user.email,
                            "role": user.role,
                            "created_at": user.created_at.isoformat() if user.created_at else None
                        }
                        for user in recent_users
                    ],
                    "documents": [
                        {
                            "id": doc.id,
                            "title": doc.title,
                            "user_id": doc.user_id,
                            "created_at": doc.created_at.isoformat() if doc.created_at else None
                        }
                        for doc in recent_documents
                    ],
                    "payments": [
                        {
                            "id": payment.id,
                            "amount": float(payment.amount),
                            "status": payment.status,
                            "user_id": payment.user_id,
                            "created_at": payment.created_at.isoformat() if payment.created_at else None
                        }
                        for payment in recent_payments
                    ]
                }
            }

        except Exception as e:
            logger.error(f"Failed to get dashboard stats: {e}")
            raise

    @staticmethod
    def track_page_visit(
        db: Session,
        page_path: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        referrer: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Track page visits for analytics"""
        try:
            visit = PageVisit(
                page_path=page_path,
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                referrer=referrer,
                device_type=device_info.get("device_type") if device_info else None,
                browser=device_info.get("browser") if device_info else None,
                country=device_info.get("country") if device_info else None,
                city=device_info.get("city") if device_info else None
            )

            db.add(visit)
            db.commit()
            db.refresh(visit)

            return {
                "success": True,
                "visit_id": visit.id,
                "message": "Page visit tracked"
            }

        except Exception as e:
            logger.error(f"Failed to track page visit: {e}")
            raise

    @staticmethod
    def create_document_share(
        db: Session,
        document_id: int,
        shared_by: int,
        hours_valid: int = 5,
        max_views: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a time-limited shareable link for document preview
        """
        try:
            import secrets
            import string

            # Generate secure share token
            share_token = ''.join(secrets.choice(
                string.ascii_letters + string.digits
            ) for _ in range(32))

            # Generate auto password
            password = ''.join(secrets.choice(
                string.ascii_uppercase + string.digits
            ) for _ in range(8))

            # Calculate expiration
            expires_at = datetime.utcnow() + timedelta(hours=hours_valid)

            # Create share record
            share = DocumentShare(
                document_id=document_id,
                shared_by=shared_by,
                share_token=share_token,
                share_password=password,
                expires_at=expires_at,
                max_views=max_views
            )

            db.add(share)
            db.commit()
            db.refresh(share)

            # Generate shareable URL
            share_url = f"/shared/{share_token}"

            logger.info(f"Document share created: {share.id} for document {document_id}")

            return {
                "success": True,
                "share_id": share.id,
                "share_token": share_token,
                "share_url": share_url,
                "password": password,
                "expires_at": expires_at.isoformat(),
                "expires_in_hours": hours_valid,
                "max_views": max_views,
                "message": f"Document share link created. Valid for {hours_valid} hours."
            }

        except Exception as e:
            logger.error(f"Failed to create document share: {e}")
            raise

    @staticmethod
    def access_shared_document(
        db: Session,
        share_token: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Access a shared document with token and password
        """
        try:
            # Find share record
            share = db.query(DocumentShare).filter(
                DocumentShare.share_token == share_token,
                DocumentShare.is_active == True
            ).first()

            if not share:
                return {
                    "success": False,
                    "error": "Share link not found or expired"
                }

            # Check expiration
            if datetime.utcnow() > share.expires_at:
                share.is_active = False
                db.commit()
                return {
                    "success": False,
                    "error": "Share link has expired"
                }

            # Check password
            if share.share_password and share.share_password != password:
                # Log failed access attempt
                access_log = json.loads(share.access_log) if share.access_log else []
                access_log.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "ip_address": ip_address,
                    "status": "failed_password",
                    "error": "Invalid password"
                })
                share.access_log = json.dumps(access_log)
                db.commit()

                return {
                    "success": False,
                    "error": "Invalid password"
                }

            # Check view limit
            if share.max_views and share.current_views >= share.max_views:
                return {
                    "success": False,
                    "error": "Maximum views reached"
                }

            # Get document
            document = db.query(Document).filter(
                Document.id == share.document_id
            ).first()

            if not document:
                return {
                    "success": False,
                    "error": "Document not found"
                }

            # Update access tracking
            share.current_views += 1
            share.last_accessed = datetime.utcnow()

            # Log successful access
            access_log = json.loads(share.access_log) if share.access_log else []
            access_log.append({
                "timestamp": datetime.utcnow().isoformat(),
                "ip_address": ip_address,
                "status": "success",
                "view_number": share.current_views
            })
            share.access_log = json.dumps(access_log)

            db.commit()

            return {
                "success": True,
                "document": {
                    "id": document.id,
                    "title": document.title,
                    "content": document.content,
                    "file_path": document.file_path,
                    "created_at": document.created_at.isoformat() if document.created_at else None
                },
                "share_info": {
                    "expires_at": share.expires_at.isoformat(),
                    "views_remaining": (share.max_views - share.current_views) if share.max_views else None,
                    "current_views": share.current_views
                },
                "view_only": True,
                "message": "Document accessed successfully"
            }

        except Exception as e:
            logger.error(f"Failed to access shared document: {e}")
            raise

    @staticmethod
    def get_page_analytics(
        db: Session,
        days: int = 30,
        page_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed page analytics
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            query = db.query(PageVisit).filter(
                PageVisit.created_at >= start_date
            )

            if page_path:
                query = query.filter(PageVisit.page_path == page_path)

            visits = query.all()

            # Calculate analytics
            total_visits = len(visits)
            unique_visitors = len(set(v.user_id for v in visits if v.user_id))
            unique_sessions = len(set(v.session_id for v in visits if v.session_id))

            # Average visit duration
            durations = [v.visit_duration for v in visits if v.visit_duration > 0]
            avg_duration = sum(durations) / len(durations) if durations else 0

            # Daily breakdown
            daily_stats = {}
            for visit in visits:
                date_key = visit.created_at.date().isoformat()
                if date_key not in daily_stats:
                    daily_stats[date_key] = {"visits": 0, "unique_users": set()}
                daily_stats[date_key]["visits"] += 1
                if visit.user_id:
                    daily_stats[date_key]["unique_users"].add(visit.user_id)

            # Convert sets to counts
            for date_key in daily_stats:
                daily_stats[date_key]["unique_users"] = len(daily_stats[date_key]["unique_users"])

            # Top referrers
            referrer_stats = {}
            for visit in visits:
                if visit.referrer:
                    referrer_stats[visit.referrer] = referrer_stats.get(visit.referrer, 0) + 1

            top_referrers = sorted(referrer_stats.items(), key=lambda x: x[1], reverse=True)[:10]

            return {
                "success": True,
                "period_days": days,
                "page_path": page_path,
                "summary": {
                    "total_visits": total_visits,
                    "unique_visitors": unique_visitors,
                    "unique_sessions": unique_sessions,
                    "average_duration_seconds": round(avg_duration, 2),
                    "bounce_rate": 0  # Would need additional tracking for this
                },
                "daily_breakdown": daily_stats,
                "top_referrers": [
                    {"referrer": ref, "visits": count}
                    for ref, count in top_referrers
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get page analytics: {e}")
            raise

    @staticmethod
    def get_user_management_data(
        db: Session,
        page: int = 1,
        limit: int = 50,
        search: Optional[str] = None,
        role_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive user management data for admin
        """
        try:
            query = db.query(User)

            # Apply filters
            if search:
                query = query.filter(or_(
                    User.email.ilike(f"%{search}%"),
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%")
                ))

            if role_filter:
                query = query.filter(User.role == role_filter)

            # Get total count
            total_users = query.count()

            # Apply pagination
            offset = (page - 1) * limit
            users = query.offset(offset).limit(limit).all()

            # Get additional user statistics
            user_data = []
            for user in users:
                # Get user's document count
                doc_count = db.query(Document).filter(Document.user_id == user.id).count()

                # Get user's total spending
                total_spent = db.query(func.sum(Payment.amount)).filter(
                    Payment.user_id == user.id,
                    Payment.status == "completed"
                ).scalar() or 0

                # Get last activity
                last_visit = db.query(PageVisit).filter(
                    PageVisit.user_id == user.id
                ).order_by(desc(PageVisit.created_at)).first()

                user_data.append({
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "document_count": doc_count,
                    "total_spent": float(total_spent),
                    "last_visit": last_visit.created_at.isoformat() if last_visit else None
                })

            return {
                "success": True,
                "users": user_data,
                "pagination": {
                    "total": total_users,
                    "page": page,
                    "limit": limit,
                    "total_pages": (total_users + limit - 1) // limit
                }
            }

        except Exception as e:
            logger.error(f"Failed to get user management data: {e}")
            raise
