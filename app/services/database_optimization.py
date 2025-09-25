"""
Database Performance Optimization System
Implements intelligent indexing, query optimization, connection pooling,
and database performance monitoring for enterprise-scale operations.
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

from sqlalchemy import text, Index, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.declarative import declarative_base

from database import engine, SessionLocal
from config import settings

# Configure logging
db_logger = logging.getLogger('database_optimization')

@dataclass
class QueryPerformanceMetric:
    """Query performance tracking"""
    query_hash: str
    sql_text: str
    execution_time_ms: float
    execution_count: int
    average_time_ms: float
    slowest_time_ms: float
    last_executed: datetime
    table_accessed: List[str]

@dataclass
class DatabaseMetrics:
    """Database performance metrics"""
    connection_pool_size: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    total_queries: int = 0
    slow_queries: int = 0
    average_query_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    index_usage_stats: Dict[str, Any] = None

class QueryOptimizer:
    """
    Intelligent query optimization and performance monitoring
    """
    
    def __init__(self):
        self.query_metrics = {}
        self.slow_query_threshold = 1000  # 1 second
        self.optimization_suggestions = {}
        
    def track_query_performance(self, sql_text: str, execution_time: float):
        """Track query performance for optimization insights"""
        query_hash = self._generate_query_hash(sql_text)
        
        if query_hash in self.query_metrics:
            metric = self.query_metrics[query_hash]
            metric.execution_count += 1
            metric.average_time_ms = (
                (metric.average_time_ms * (metric.execution_count - 1) + execution_time) 
                / metric.execution_count
            )
            metric.slowest_time_ms = max(metric.slowest_time_ms, execution_time)
            metric.last_executed = datetime.utcnow()
        else:
            self.query_metrics[query_hash] = QueryPerformanceMetric(
                query_hash=query_hash,
                sql_text=sql_text[:500],  # Truncate long queries
                execution_time_ms=execution_time,
                execution_count=1,
                average_time_ms=execution_time,
                slowest_time_ms=execution_time,
                last_executed=datetime.utcnow(),
                table_accessed=self._extract_tables_from_query(sql_text)
            )
        
        # Log slow queries
        if execution_time > self.slow_query_threshold:
            db_logger.warning(f"Slow query detected: {execution_time:.2f}ms - {sql_text[:200]}")
    
    def get_optimization_suggestions(self) -> List[Dict[str, Any]]:
        """Generate database optimization suggestions"""
        suggestions = []
        
        # Analyze slow queries
        for metric in self.query_metrics.values():
            if metric.average_time_ms > self.slow_query_threshold:
                suggestions.append({
                    'type': 'slow_query',
                    'severity': 'high' if metric.average_time_ms > 5000 else 'medium',
                    'message': f"Query averaging {metric.average_time_ms:.2f}ms needs optimization",
                    'sql_snippet': metric.sql_text[:200],
                    'recommendation': self._generate_query_recommendation(metric),
                    'tables': metric.table_accessed
                })
        
        # Check for missing indexes
        missing_indexes = self._suggest_missing_indexes()
        for index_suggestion in missing_indexes:
            suggestions.append({
                'type': 'missing_index',
                'severity': 'medium',
                'message': f"Consider adding index on {index_suggestion['table']}.{index_suggestion['column']}",
                'recommendation': f"CREATE INDEX idx_{index_suggestion['table']}_{index_suggestion['column']} ON {index_suggestion['table']} ({index_suggestion['column']});",
                'impact': index_suggestion.get('impact', 'medium')
            })
        
        return suggestions
    
    def _generate_query_hash(self, sql_text: str) -> str:
        """Generate hash for query identification"""
        import hashlib
        # Normalize query text
        normalized = sql_text.strip().lower()
        # Remove variable parts (numbers, strings)
        import re
        normalized = re.sub(r'\d+', 'N', normalized)
        normalized = re.sub(r"'[^']*'", "'X'", normalized)
        
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _extract_tables_from_query(self, sql_text: str) -> List[str]:
        """Extract table names from SQL query"""
        import re
        # Simple regex to find table names (can be improved)
        tables = re.findall(r'FROM\s+(\w+)|JOIN\s+(\w+)|UPDATE\s+(\w+)|INTO\s+(\w+)', 
                           sql_text.upper())
        
        # Flatten and filter
        table_names = []
        for match in tables:
            for table in match:
                if table:
                    table_names.append(table.lower())
        
        return list(set(table_names))
    
    def _generate_query_recommendation(self, metric: QueryPerformanceMetric) -> str:
        """Generate optimization recommendation for query"""
        sql_lower = metric.sql_text.lower()
        
        if 'order by' in sql_lower and 'limit' in sql_lower:
            return "Consider adding composite index for ORDER BY + LIMIT queries"
        elif 'where' in sql_lower and 'join' in sql_lower:
            return "Optimize JOIN conditions and consider indexing foreign keys"
        elif 'group by' in sql_lower:
            return "Add indexes on GROUP BY columns"
        elif 'like' in sql_lower:
            return "Consider full-text search or prefix indexes for LIKE queries"
        else:
            return "Review query structure and add appropriate indexes"
    
    def _suggest_missing_indexes(self) -> List[Dict[str, Any]]:
        """Suggest missing indexes based on query patterns"""
        suggestions = []
        
        # Analyze WHERE clauses from tracked queries
        where_columns = {}
        for metric in self.query_metrics.values():
            sql_lower = metric.sql_text.lower()
            if 'where' in sql_lower:
                # Extract potential index candidates
                import re
                where_matches = re.findall(r'where\s+(\w+)', sql_lower)
                for match in where_matches:
                    if match not in where_columns:
                        where_columns[match] = 0
                    where_columns[match] += metric.execution_count
        
        # Suggest indexes for frequently queried columns
        for column, usage_count in where_columns.items():
            if usage_count > 10:  # Threshold for index suggestion
                suggestions.append({
                    'table': 'unknown',  # Would need more sophisticated parsing
                    'column': column,
                    'impact': 'high' if usage_count > 100 else 'medium',
                    'usage_count': usage_count
                })
        
        return suggestions[:5]  # Return top 5 suggestions

class DatabaseOptimizationManager:
    """
    Comprehensive database optimization and monitoring system
    """
    
    def __init__(self):
        self.query_optimizer = QueryOptimizer()
        self.metrics = DatabaseMetrics()
        self.optimization_enabled = True
        
        # Setup query monitoring
        self._setup_query_monitoring()
        
        # Start monitoring tasks
        asyncio.create_task(self._performance_monitoring_loop())
        asyncio.create_task(self._optimization_maintenance_loop())
    
    def _setup_query_monitoring(self):
        """Setup automatic query performance monitoring"""
        
        @event.listens_for(engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if hasattr(context, '_query_start_time'):
                execution_time = (time.time() - context._query_start_time) * 1000
                self.query_optimizer.track_query_performance(statement, execution_time)
    
    async def optimize_database_schema(self, db: Session) -> Dict[str, Any]:
        """
        Perform comprehensive database schema optimization
        """
        optimization_results = {
            'indexes_created': 0,
            'indexes_removed': 0,
            'tables_analyzed': 0,
            'performance_improvement': 0.0,
            'recommendations': []
        }
        
        try:
            # Analyze current performance
            before_stats = await self._collect_performance_stats(db)
            
            # Create recommended indexes
            index_suggestions = await self._create_performance_indexes(db)
            optimization_results['indexes_created'] = len(index_suggestions)
            
            # Remove unused indexes
            removed_indexes = await self._remove_unused_indexes(db)
            optimization_results['indexes_removed'] = len(removed_indexes)
            
            # Analyze tables
            table_stats = await self._analyze_table_statistics(db)
            optimization_results['tables_analyzed'] = len(table_stats)
            
            # Update table statistics
            await self._update_table_statistics(db)
            
            # Collect after stats
            after_stats = await self._collect_performance_stats(db)
            
            # Calculate improvement
            if before_stats['average_query_time'] > 0:
                improvement = (
                    (before_stats['average_query_time'] - after_stats['average_query_time']) 
                    / before_stats['average_query_time'] * 100
                )
                optimization_results['performance_improvement'] = improvement
            
            # Generate recommendations
            optimization_results['recommendations'] = self.query_optimizer.get_optimization_suggestions()
            
            db_logger.info(f"Database optimization completed: {optimization_results}")
            return optimization_results
            
        except Exception as e:
            db_logger.error(f"Database optimization failed: {e}")
            return {'error': str(e)}
    
    async def _create_performance_indexes(self, db: Session) -> List[str]:
        """Create performance-optimized indexes"""
        created_indexes = []
        
        try:
            # Critical indexes for MyTypist application
            index_definitions = [
                # User-related indexes
                ("idx_users_email", "users", ["email"]),
                ("idx_users_created_at", "users", ["created_at"]),
                
                # Template indexes
                ("idx_templates_created_by", "templates", ["created_by"]),
                ("idx_templates_category", "templates", ["category"]),
                ("idx_templates_is_public", "templates", ["is_public"]),
                ("idx_templates_created_at", "templates", ["created_at"]),
                
                # Document indexes
                ("idx_documents_user_id", "documents", ["user_id"]),
                ("idx_documents_template_id", "documents", ["template_id"]),
                ("idx_documents_status", "documents", ["status"]),
                ("idx_documents_created_at", "documents", ["created_at"]),
                
                # Signature indexes
                ("idx_signatures_user_id", "signatures", ["user_id"]),
                ("idx_signatures_document_id", "signatures", ["document_id"]),
                ("idx_signatures_created_at", "signatures", ["created_at"]),
                
                # Audit indexes
                ("idx_audit_logs_user_id", "audit_logs", ["user_id"]),
                ("idx_audit_logs_event_type", "audit_logs", ["event_type"]),
                ("idx_audit_logs_created_at", "audit_logs", ["created_at"]),
                
                # Payment indexes
                ("idx_payments_user_id", "payments", ["user_id"]),
                ("idx_payments_status", "payments", ["status"]),
                ("idx_payments_created_at", "payments", ["created_at"]),
                
                # Visit indexes
                ("idx_visits_user_id", "visits", ["user_id"]),
                ("idx_visits_ip_address", "visits", ["ip_address"]),
                ("idx_visits_created_at", "visits", ["created_at"]),
                
                # Composite indexes for common queries
                ("idx_documents_user_status", "documents", ["user_id", "status"]),
                ("idx_templates_public_category", "templates", ["is_public", "category"]),
                ("idx_audit_user_event_date", "audit_logs", ["user_id", "event_type", "created_at"]),
            ]
            
            # Create indexes if they don't exist
            for index_name, table_name, columns in index_definitions:
                try:
                    # Check if index exists
                    check_query = """
                    SELECT 1 FROM pg_indexes 
                    WHERE indexname = :index_name AND tablename = :table_name
                    """
                    result = db.execute(text(check_query), {"index_name": index_name, "table_name": table_name}).fetchone()
                    
                    if not result:
                        # Create index with proper identifier quoting
                        columns_str = ", ".join(f'"{col}"' for col in columns)
                        create_query = f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" ON "{table_name}" ({columns_str})'
                        
                        db.execute(text(create_query))
                        db.commit()
                        
                        created_indexes.append(index_name)
                        db_logger.info(f"Created index: {index_name}")
                        
                except Exception as e:
                    db_logger.error(f"Failed to create index {index_name}: {e}")
                    db.rollback()
            
        except Exception as e:
            db_logger.error(f"Index creation failed: {e}")
        
        return created_indexes
    
    async def _remove_unused_indexes(self, db: Session) -> List[str]:
        """Remove unused indexes to improve write performance"""
        removed_indexes = []
        
        try:
            # Find unused indexes (PostgreSQL specific)
            unused_query = """
            SELECT indexrelname as index_name
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0 
            AND indexrelname NOT LIKE '%_pkey'
            AND indexrelname NOT LIKE '%_key'
            """
            
            result = db.execute(text(unused_query)).fetchall()
            
            for row in result:
                index_name = row[0]
                try:
                    # Don't remove recently created indexes
                    if not any(created in index_name for created in ['_created_at', '_id']):
                        # Validate identifier and add proper quoting
                        if index_name.replace('_', '').replace('-', '').isalnum():
                            # Use parameterized query to prevent SQL injection
                            drop_query = 'DROP INDEX CONCURRENTLY IF EXISTS "' + index_name.replace('"', '""') + '"'
                            db.execute(text(drop_query))
                            db.commit()
                            
                            removed_indexes.append(index_name)
                            db_logger.info(f"Removed unused index: {index_name}")
                        
                except Exception as e:
                    db_logger.error(f"Failed to remove index {index_name}: {e}")
                    db.rollback()
        
        except Exception as e:
            db_logger.error(f"Index removal failed: {e}")
        
        return removed_indexes
    
    async def _analyze_table_statistics(self, db: Session) -> List[str]:
        """Analyze table statistics for query optimization"""
        analyzed_tables = []
        
        try:
            # Get all user tables
            tables_query = """
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            """
            
            result = db.execute(text(tables_query)).fetchall()
            
            for row in result:
                table_name = row[0]
                try:
                    # Validate identifier and analyze table with proper quoting
                    if table_name.replace('_', '').isalnum():
                        # Use safe identifier quoting to prevent SQL injection
                        analyze_query = 'ANALYZE "' + table_name.replace('"', '""') + '"'
                        db.execute(text(analyze_query))
                        analyzed_tables.append(table_name)
                    
                except Exception as e:
                    db_logger.error(f"Failed to analyze table {table_name}: {e}")
            
            db.commit()
            
        except Exception as e:
            db_logger.error(f"Table analysis failed: {e}")
        
        return analyzed_tables
    
    async def _update_table_statistics(self, db: Session):
        """Update table statistics for better query planning"""
        try:
            # Update PostgreSQL statistics
            db.execute(text("ANALYZE"))
            db.commit()
            db_logger.info("Updated table statistics")
            
        except Exception as e:
            db_logger.error(f"Statistics update failed: {e}")
    
    async def _collect_performance_stats(self, db: Session) -> Dict[str, float]:
        """Collect current database performance statistics"""
        stats = {
            'active_connections': 0,
            'average_query_time': 0.0,
            'cache_hit_rate': 0.0,
            'index_usage': 0.0
        }
        
        try:
            # Get connection stats
            conn_query = "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
            result = db.execute(text(conn_query)).fetchone()
            stats['active_connections'] = result[0] if result else 0
            
            # Get cache hit rate
            cache_query = """
            SELECT round(
                sum(blks_hit) * 100.0 / sum(blks_hit + blks_read), 2
            ) as cache_hit_rate
            FROM pg_stat_database
            """
            result = db.execute(text(cache_query)).fetchone()
            stats['cache_hit_rate'] = result[0] if result else 0.0
            
            # Calculate average query time from tracked metrics
            if self.query_optimizer.query_metrics:
                avg_time = sum(
                    metric.average_time_ms 
                    for metric in self.query_optimizer.query_metrics.values()
                ) / len(self.query_optimizer.query_metrics)
                stats['average_query_time'] = avg_time
            
        except Exception as e:
            db_logger.error(f"Performance stats collection failed: {e}")
        
        return stats
    
    async def _performance_monitoring_loop(self):
        """Background performance monitoring"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Update metrics
                db = SessionLocal()
                try:
                    current_stats = await self._collect_performance_stats(db)
                    
                    # Update metrics object
                    self.metrics.active_connections = current_stats['active_connections']
                    self.metrics.average_query_time_ms = current_stats['average_query_time']
                    self.metrics.cache_hit_rate = current_stats['cache_hit_rate']
                    
                    # Log performance summary
                    db_logger.info(
                        f"DB Performance - Active: {self.metrics.active_connections}, "
                        f"Avg Query: {self.metrics.average_query_time_ms:.2f}ms, "
                        f"Cache Hit: {self.metrics.cache_hit_rate:.1f}%"
                    )
                    
                finally:
                    db.close()
                    
            except Exception as e:
                db_logger.error(f"Performance monitoring error: {e}")
    
    async def _optimization_maintenance_loop(self):
        """Background optimization maintenance"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Run maintenance if enabled
                if self.optimization_enabled:
                    db = SessionLocal()
                    try:
                        # Update statistics
                        await self._update_table_statistics(db)
                        
                        # Check for optimization opportunities
                        suggestions = self.query_optimizer.get_optimization_suggestions()
                        if len(suggestions) > 5:
                            db_logger.warning(
                                f"Found {len(suggestions)} optimization opportunities"
                            )
                    finally:
                        db.close()
                
            except Exception as e:
                db_logger.error(f"Optimization maintenance error: {e}")
    
    def get_database_metrics(self) -> Dict[str, Any]:
        """Get comprehensive database metrics"""
        
        # Get connection pool stats
        pool = engine.pool
        pool_stats = {
            'pool_size': pool.size(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'checked_in': pool.checkedin()
        }
        
        # Get query performance stats
        total_queries = sum(m.execution_count for m in self.query_optimizer.query_metrics.values())
        slow_queries = sum(
            1 for m in self.query_optimizer.query_metrics.values() 
            if m.average_time_ms > self.query_optimizer.slow_query_threshold
        )
        
        return {
            'connection_pool': pool_stats,
            'query_performance': {
                'total_queries': total_queries,
                'slow_queries': slow_queries,
                'average_time_ms': self.metrics.average_query_time_ms,
                'cache_hit_rate': self.metrics.cache_hit_rate
            },
            'optimization_suggestions': len(self.query_optimizer.get_optimization_suggestions()),
            'monitoring_enabled': self.optimization_enabled
        }

# Global database optimization manager
db_optimizer = DatabaseOptimizationManager()