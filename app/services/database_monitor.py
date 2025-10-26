import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.config.db import get_db
from app.config.settings import settings

logger = logging.getLogger(__name__)

class DatabaseMonitor:
    """
    Database monitoring service for performance tracking and health checks
    """
    
    def __init__(self):
        self.performance_history: List[Dict] = []
        self.alert_thresholds = {
            "query_time_ms": 1000,  # Alert if query takes more than 1 second
            "connection_pool_usage": 0.8,  # Alert if pool usage > 80%
            "error_rate": 0.05  # Alert if error rate > 5%
        }
    
    async def get_connection_pool_status(self, db: Session) -> Dict:
        """
        Get current connection pool status
        """
        try:
            pool = db.get_bind().pool
            pool_size = getattr(pool, 'size', 0)
            checked_in = getattr(pool, 'checkedin', 0)
            checked_out = getattr(pool, 'checkedout', 0)
            overflow = getattr(pool, 'overflow', 0)
            invalid = getattr(pool, 'invalid', 0)
            
            total_connections = pool_size + overflow
            active_connections = checked_out
            usage_percentage = (active_connections / total_connections) * 100 if total_connections > 0 else 0
            
            return {
                "pool_size": pool_size,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "overflow": overflow,
                "invalid": invalid,
                "total_connections": total_connections,
                "active_connections": active_connections,
                "usage_percentage": round(usage_percentage, 2),
                "status": "healthy" if usage_percentage < 80 else "warning" if usage_percentage < 95 else "critical"
            }
        except Exception as e:
            logger.error(f"Failed to get connection pool status: {e}")
            return {"status": "error", "error": str(e)}
    
    async def test_query_performance(self, db: Session) -> Dict:
        """
        Test database query performance with various query types
        """
        performance_results = {}
        
        # Test 1: Simple SELECT
        start_time = time.time()
        try:
            db.execute(text("SELECT 1")).scalar()
            simple_query_time = (time.time() - start_time) * 1000
            performance_results["simple_select_ms"] = round(simple_query_time, 2)
        except Exception as e:
            performance_results["simple_select_ms"] = None
            performance_results["simple_select_error"] = str(e)
        
        # Test 2: Count query
        start_time = time.time()
        try:
            db.execute(text("SELECT COUNT(*) FROM companies LIMIT 1")).scalar()
            count_query_time = (time.time() - start_time) * 1000
            performance_results["count_query_ms"] = round(count_query_time, 2)
        except Exception as e:
            performance_results["count_query_ms"] = None
            performance_results["count_query_error"] = str(e)
        
        # Test 3: Complex JOIN query (if tables exist)
        start_time = time.time()
        try:
            # Test a more complex query if we have the data
            result = db.execute(text("""
                SELECT COUNT(*) 
                FROM companies c 
                LEFT JOIN users u ON c.id = u.companyid 
                LIMIT 1
            """)).scalar()
            join_query_time = (time.time() - start_time) * 1000
            performance_results["join_query_ms"] = round(join_query_time, 2)
        except Exception as e:
            performance_results["join_query_ms"] = None
            performance_results["join_query_error"] = str(e)
        
        return performance_results
    
    async def get_database_stats(self, db: Session) -> Dict:
        """
        Get general database statistics
        """
        stats = {}
        
        try:
            # Get table counts
            tables_to_check = ['companies', 'users', 'drivers', 'equipment', 'simple_loads']
            for table in tables_to_check:
                try:
                    result = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    stats[f"{table}_count"] = result
                except Exception as e:
                    stats[f"{table}_count"] = f"Error: {str(e)}"
            
            # Get database size (PostgreSQL specific)
            try:
                if 'postgresql' in settings.DATABASE_URL:
                    size_result = db.execute(text("""
                        SELECT pg_size_pretty(pg_database_size(current_database()))
                    """)).scalar()
                    stats["database_size"] = size_result
            except Exception as e:
                stats["database_size"] = f"Error: {str(e)}"
            
            # Get connection count (PostgreSQL specific)
            try:
                if 'postgresql' in settings.DATABASE_URL:
                    conn_result = db.execute(text("""
                        SELECT count(*) FROM pg_stat_activity 
                        WHERE state = 'active'
                    """)).scalar()
                    stats["active_connections"] = conn_result
            except Exception as e:
                stats["active_connections"] = f"Error: {str(e)}"
                
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            stats["error"] = str(e)
        
        return stats
    
    async def check_for_slow_queries(self, db: Session) -> List[Dict]:
        """
        Check for slow queries (PostgreSQL specific)
        """
        slow_queries = []
        
        try:
            if 'postgresql' in settings.DATABASE_URL:
                # Get slow queries from pg_stat_statements (if available)
                result = db.execute(text("""
                    SELECT query, calls, total_time, mean_time
                    FROM pg_stat_statements 
                    WHERE mean_time > 1000  -- Queries taking more than 1 second on average
                    ORDER BY mean_time DESC 
                    LIMIT 10
                """)).fetchall()
                
                for row in result:
                    slow_queries.append({
                        "query": row[0][:100] + "..." if len(row[0]) > 100 else row[0],  # Truncate long queries
                        "calls": row[1],
                        "total_time_ms": round(row[2], 2),
                        "mean_time_ms": round(row[3], 2)
                    })
        except Exception as e:
            logger.warning(f"Could not check for slow queries: {e}")
            # pg_stat_statements might not be available
        
        return slow_queries
    
    async def get_full_health_report(self, db: Session) -> Dict:
        """
        Generate a comprehensive database health report
        """
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "database_url": settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else "configured",  # Hide credentials
            "ssl_mode": getattr(settings, 'DB_SSL_MODE', 'not_configured'),
            "environment": settings.ENVIRONMENT
        }
        
        # Get connection pool status
        report["connection_pool"] = await self.get_connection_pool_status(db)
        
        # Get performance metrics
        report["performance"] = await self.test_query_performance(db)
        
        # Get database statistics
        report["statistics"] = await self.get_database_stats(db)
        
        # Check for slow queries
        report["slow_queries"] = await self.check_for_slow_queries(db)
        
        # Overall health assessment
        health_score = 100
        
        # Deduct points for performance issues
        if report["performance"].get("simple_select_ms", 0) > 100:
            health_score -= 20
        if report["performance"].get("count_query_ms", 0) > 500:
            health_score -= 30
        if report["connection_pool"].get("usage_percentage", 0) > 80:
            health_score -= 25
        if len(report["slow_queries"]) > 0:
            health_score -= 15
        
        report["health_score"] = max(0, health_score)
        report["overall_status"] = (
            "excellent" if health_score >= 90 else
            "good" if health_score >= 70 else
            "fair" if health_score >= 50 else
            "poor" if health_score >= 30 else
            "critical"
        )
        
        return report

# Global instance
db_monitor = DatabaseMonitor()

