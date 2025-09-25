"""
Production monitoring and alerting service
"""

import time
import asyncio
import psutil
from typing import Dict, Any, List
from datetime import datetime, timedelta

from app.services.cache_service import cache_service
from app.services.audit_service import AuditService
from database import DatabaseManager


class ProductionMonitor:
    """Comprehensive production monitoring"""
    
    def __init__(self):
        self.alert_thresholds = {
            "cpu_usage": 80,           # CPU > 80%
            "memory_usage": 85,        # Memory > 85%
            "disk_usage": 90,          # Disk > 90%
            "response_time": 1000,     # Response > 1 second
            "error_rate": 5,           # Error rate > 5%
            "db_pool_usage": 90        # DB pool > 90%
        }
    
    async def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024**3)
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent()
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "system": {
                    "cpu_percent": cpu_percent,
                    "cpu_count": cpu_count,
                    "memory_percent": memory_percent,
                    "memory_available_gb": round(memory_available_gb, 2),
                    "disk_percent": round(disk_percent, 2),
                    "disk_free_gb": round(disk_free_gb, 2)
                },
                "process": {
                    "memory_mb": round(process_memory.rss / (1024**2), 2),
                    "cpu_percent": process_cpu,
                    "threads": process.num_threads()
                }
            }
        except Exception as e:
            return {"error": f"Failed to collect metrics: {e}"}
    
    async def collect_application_metrics(self) -> Dict[str, Any]:
        """Collect application-specific metrics"""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "database": {},
            "cache": {},
            "performance": {}
        }
        
        # Database metrics
        try:
            pool_status = DatabaseManager.get_pool_status()
            total_connections = pool_status["pool_size"] + pool_status["overflow"]
            utilization = (pool_status["checked_out"] / total_connections * 100) if total_connections > 0 else 0
            
            metrics["database"] = {
                "pool_utilization": round(utilization, 2),
                "active_connections": pool_status["checked_out"],
                "total_connections": total_connections,
                "health": "healthy" if utilization < 80 else "warning" if utilization < 95 else "critical"
            }
        except Exception as e:
            metrics["database"] = {"error": str(e)}
        
        # Cache metrics
        try:
            if cache_service.redis:
                info = await cache_service.redis.info()
                metrics["cache"] = {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_mb": round(info.get("used_memory", 0) / (1024**2), 2),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                    "hit_rate": self._calculate_hit_rate(info)
                }
            else:
                metrics["cache"] = {"status": "unavailable"}
        except Exception as e:
            metrics["cache"] = {"error": str(e)}
        
        return metrics
    
    def _calculate_hit_rate(self, redis_info: Dict) -> float:
        """Calculate cache hit rate"""
        hits = redis_info.get("keyspace_hits", 0)
        misses = redis_info.get("keyspace_misses", 0)
        total = hits + misses
        return round((hits / total * 100) if total > 0 else 0, 2)
    
    async def check_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for alert conditions"""
        alerts = []
        
        # System alerts
        system_metrics = metrics.get("system", {})
        if system_metrics.get("cpu_percent", 0) > self.alert_thresholds["cpu_usage"]:
            alerts.append({
                "type": "HIGH_CPU_USAGE",
                "severity": "warning",
                "message": f"CPU usage at {system_metrics['cpu_percent']}%",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        if system_metrics.get("memory_percent", 0) > self.alert_thresholds["memory_usage"]:
            alerts.append({
                "type": "HIGH_MEMORY_USAGE",
                "severity": "warning",
                "message": f"Memory usage at {system_metrics['memory_percent']}%",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        if system_metrics.get("disk_percent", 0) > self.alert_thresholds["disk_usage"]:
            alerts.append({
                "type": "HIGH_DISK_USAGE",
                "severity": "critical",
                "message": f"Disk usage at {system_metrics['disk_percent']}%",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # Database alerts
        db_metrics = metrics.get("database", {})
        if db_metrics.get("pool_utilization", 0) > self.alert_thresholds["db_pool_usage"]:
            alerts.append({
                "type": "HIGH_DB_POOL_USAGE",
                "severity": "critical",
                "message": f"Database pool at {db_metrics['pool_utilization']}% utilization",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return alerts
    
    async def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        print("📊 Generating performance report...")
        
        # Collect metrics
        system_metrics = await self.collect_system_metrics()
        app_metrics = await self.collect_application_metrics()
        
        # Combine metrics
        all_metrics = {**system_metrics, **app_metrics}
        
        # Check for alerts
        alerts = await self.check_alerts(all_metrics)
        
        # Performance score calculation
        score = self._calculate_performance_score(all_metrics)
        
        report = {
            "report_timestamp": datetime.utcnow().isoformat(),
            "performance_score": score,
            "metrics": all_metrics,
            "alerts": alerts,
            "recommendations": self._generate_recommendations(all_metrics, alerts)
        }
        
        return report
    
    def _calculate_performance_score(self, metrics: Dict[str, Any]) -> int:
        """Calculate overall performance score (0-100)"""
        score = 100
        
        # Deduct points for high resource usage
        system = metrics.get("system", {})
        score -= max(0, (system.get("cpu_percent", 0) - 50) * 2)
        score -= max(0, (system.get("memory_percent", 0) - 60) * 2)
        score -= max(0, (system.get("disk_percent", 0) - 70) * 3)
        
        # Deduct points for database issues
        db = metrics.get("database", {})
        if "error" in db:
            score -= 30
        else:
            pool_util = db.get("pool_utilization", 0)
            score -= max(0, (pool_util - 70) * 2)
        
        # Deduct points for cache issues
        cache = metrics.get("cache", {})
        if "error" in cache:
            score -= 20
        elif cache.get("status") == "unavailable":
            score -= 10
        
        return max(0, min(100, int(score)))
    
    def _generate_recommendations(self, metrics: Dict[str, Any], alerts: List[Dict]) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        if alerts:
            recommendations.append("Address critical alerts immediately")
        
        # System recommendations
        system = metrics.get("system", {})
        if system.get("cpu_percent", 0) > 70:
            recommendations.append("Consider scaling horizontally or optimizing CPU-intensive operations")
        
        if system.get("memory_percent", 0) > 75:
            recommendations.append("Monitor memory usage and consider increasing server memory")
        
        # Database recommendations
        db = metrics.get("database", {})
        if db.get("pool_utilization", 0) > 80:
            recommendations.append("Consider increasing database connection pool size")
        
        # Cache recommendations
        cache = metrics.get("cache", {})
        if cache.get("hit_rate", 100) < 80:
            recommendations.append("Review caching strategy to improve hit rate")
        
        if not recommendations:
            recommendations.append("System is performing optimally")
        
        return recommendations


# Global monitor instance
production_monitor = ProductionMonitor()