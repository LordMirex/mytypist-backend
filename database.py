"""
Production-ready PostgreSQL database configuration and session management
Optimized for high-performance document processing with advanced connection pooling
"""

import os
import logging
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from config import settings

logger = logging.getLogger(__name__)

# Production PostgreSQL engine with maximum optimizations
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=25,                        # Increased base connection pool
    max_overflow=50,                     # Higher burst capacity
    pool_timeout=60,                     # Longer wait for connections
    pool_recycle=7200,                   # 2-hour connection lifecycle
    pool_pre_ping=True,                  # Health check before use
    pool_reset_on_return='commit',       # Clean state on return
    connect_args={
        "connect_timeout": 30,
        "application_name": "MyTypist-Production-Backend"
    },
    echo=settings.DEBUG,
    echo_pool=settings.DEBUG
)

# Conservative PostgreSQL optimizations for hosted databases
@event.listens_for(engine, "connect")
def set_postgresql_optimizations(dbapi_connection, connection_record):
    """Apply safe PostgreSQL optimizations for hosted databases"""
    try:
        with dbapi_connection.cursor() as cursor:
            # Safe session-level optimizations only
            cursor.execute("SET work_mem = '16MB'")
            cursor.execute("SET statement_timeout = '300s'")
            cursor.execute("SET lock_timeout = '30s'")

        logger.info("PostgreSQL optimizations applied successfully")
    except Exception as e:
        logger.warning(f"Failed to apply PostgreSQL optimizations: {e}")
        # Continue without optimizations rather than fail

# Connection pool monitoring
@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    """Monitor connection checkouts"""
    logger.debug(f"Connection checked out. Pool status: {engine.pool.status()}")

@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    """Monitor connection checkins"""
    logger.debug(f"Connection checked in. Pool status: {engine.pool.status()}")

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseManager:
    """Database management utilities"""

    @staticmethod
    def create_all_tables():
        """Create all database tables"""
        Base.metadata.create_all(bind=engine)

    @staticmethod
    def drop_all_tables():
        """Drop all database tables (use with caution)"""
        Base.metadata.drop_all(bind=engine)

    @staticmethod
    def get_session():
        """Get a new database session"""
        return SessionLocal()

    @staticmethod
    def close_session(session):
        """Close database session"""
        session.close()

    @staticmethod
    def get_pool_status():
        """Get connection pool status for monitoring"""
        pool = engine.pool
        return {
            "pool_size": pool.size,
            "checked_out": pool.checkedout,
            "overflow": pool.overflow,
            "checked_in": pool.checkedin
        }

    @staticmethod
    def optimize_database():
        """Run comprehensive PostgreSQL optimization commands"""
        try:
            with engine.connect() as conn:
                # Update table statistics for query planner
                conn.execute(text("ANALYZE"))

                # Full vacuum and analyze for optimal performance
                conn.execute(text("VACUUM ANALYZE"))

                # Reindex to optimize index performance
                conn.execute(text("REINDEX DATABASE CONCURRENTLY"))

                # Update extension statistics
                conn.execute(text("SELECT pg_stat_reset()"))

                # Log optimization completion
                logger.info("Database optimization completed successfully")

        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            raise

    @staticmethod
    def get_performance_stats():
        """Get comprehensive database performance statistics"""
        try:
            with engine.connect() as conn:
                # Connection pool stats
                pool_stats = {
                    "pool_size": engine.pool.size,
                    "checked_out": engine.pool.checkedout,
                    "overflow": engine.pool.overflow,
                    "checked_in": engine.pool.checkedin
                }

                # Database performance stats
                db_stats = conn.execute(text("""
                    SELECT
                        pg_database.datname,
                        pg_stat_database.numbackends,
                        pg_stat_database.xact_commit,
                        pg_stat_database.xact_rollback,
                        pg_stat_database.blks_read,
                        pg_stat_database.blks_hit,
                        pg_stat_database.tup_returned,
                        pg_stat_database.tup_fetched,
                        pg_stat_database.tup_inserted,
                        pg_stat_database.tup_updated,
                        pg_stat_database.tup_deleted
                    FROM pg_stat_database
                    JOIN pg_database ON pg_stat_database.datid = pg_database.oid
                    WHERE pg_database.datname = current_database()
                """)).fetchone()

                return {
                    "pool": pool_stats,
                    "database": dict(db_stats._mapping) if db_stats else None
                }

        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}")
            return {"error": str(e)}
