"""
Advanced Connection Pool Configuration for 5000+ Concurrent Users
"""
import os
import logging
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from app.config.settings import settings
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class ConnectionPoolManager:
    """
    Advanced connection pool management for high-scale operations
    """
    
    def __init__(self):
        self.engine = None
        self.pool_config = self._get_pool_config()
    
    def _get_pool_config(self) -> dict:
        """Get optimized pool configuration for 5000+ users"""
        return {
            # Core pool settings
            'pool_size': int(os.getenv('DB_POOL_SIZE', 50)),  # Increased for high scale
            'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', 100)),  # Allow burst connections
            'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', 30)),  # Wait time for connection
            'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', 3600)),  # Recycle connections hourly
            
            # Advanced pool settings for high scale
            'pool_pre_ping': True,  # Verify connections before use
            'pool_reset_on_return': 'commit',  # Reset connections on return
            
            # Neon-specific optimizations
            'connect_args': {
                'sslmode': 'require',
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 5,
                'channel_binding': 'require',
                'application_name': 'freightops-high-scale'
            }
        }
    
    def create_engine(self) -> Engine:
        """Create optimized database engine for high-scale operations"""
        try:
            # Base engine configuration
            engine_kwargs = {
                'poolclass': QueuePool,
                'pool_pre_ping': self.pool_config['pool_pre_ping'],
                'pool_reset_on_return': self.pool_config['pool_reset_on_return'],
                'pool_size': self.pool_config['pool_size'],
                'max_overflow': self.pool_config['max_overflow'],
                'pool_timeout': self.pool_config['pool_timeout'],
                'pool_recycle': self.pool_config['pool_recycle'],
                'echo': settings.DEBUG,  # Log SQL queries in debug mode
                'echo_pool': settings.DEBUG,  # Log pool events in debug mode
            }
            
            # Add connection arguments for Neon
            if 'neon.tech' in settings.DATABASE_URL:
                engine_kwargs['connect_args'] = self.pool_config['connect_args']
            
            # Create engine
            self.engine = create_engine(
                settings.DATABASE_URL,
                **engine_kwargs
            )
            
            # Set up event listeners for monitoring
            self._setup_event_listeners()
            
            logger.info(f"Database engine created with pool size: {self.pool_config['pool_size']}, "
                       f"max overflow: {self.pool_config['max_overflow']}")
            
            return self.engine
            
        except Exception as e:
            logger.error(f"Failed to create database engine: {e}")
            raise
    
    def _setup_event_listeners(self):
        """Set up event listeners for connection pool monitoring"""
        from sqlalchemy import event
        
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Set connection-specific parameters"""
            if 'postgresql' in settings.DATABASE_URL:
                # Set PostgreSQL connection parameters
                with dbapi_connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '30s'")
                    cursor.execute("SET idle_in_transaction_session_timeout = '60s'")
                    cursor.execute("SET lock_timeout = '10s'")
        
        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Log connection checkout events"""
            logger.debug(f"Connection checked out: {connection_proxy}")
        
        @event.listens_for(self.engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Log connection checkin events"""
            logger.debug(f"Connection checked in: {connection_record}")
        
        @event.listens_for(self.engine, "invalidate")
        def receive_invalidate(dbapi_connection, connection_record, exception):
            """Log connection invalidation events"""
            logger.warning(f"Connection invalidated: {exception}")
    
    def get_pool_status(self) -> dict:
        """Get current connection pool status"""
        if not self.engine:
            return {'error': 'Engine not initialized'}
        
        pool = self.engine.pool
        return {
            'pool_size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'invalid': pool.invalid(),
            'total_connections': pool.size() + pool.overflow(),
            'available_connections': pool.checkedin(),
            'utilization_percent': (pool.checkedout() / (pool.size() + pool.overflow())) * 100 if (pool.size() + pool.overflow()) > 0 else 0
        }
    
    def optimize_pool_for_load(self, current_connections: int, target_connections: int):
        """Dynamically optimize pool settings based on current load"""
        try:
            current_pool_size = self.pool_config['pool_size']
            current_max_overflow = self.pool_config['max_overflow']
            
            # Calculate new pool settings based on load
            if current_connections > target_connections * 0.8:
                # High load - increase pool size
                new_pool_size = min(current_pool_size + 10, 100)
                new_max_overflow = min(current_max_overflow + 20, 150)
                
                logger.info(f"High load detected. Increasing pool size to {new_pool_size}, "
                           f"max overflow to {new_max_overflow}")
                
                # Update pool configuration
                self.pool_config['pool_size'] = new_pool_size
                self.pool_config['max_overflow'] = new_max_overflow
                
            elif current_connections < target_connections * 0.3:
                # Low load - decrease pool size
                new_pool_size = max(current_pool_size - 5, 20)
                new_max_overflow = max(current_max_overflow - 10, 50)
                
                logger.info(f"Low load detected. Decreasing pool size to {new_pool_size}, "
                           f"max overflow to {new_max_overflow}")
                
                # Update pool configuration
                self.pool_config['pool_size'] = new_pool_size
                self.pool_config['max_overflow'] = new_max_overflow
            
            return True
            
        except Exception as e:
            logger.error(f"Pool optimization error: {e}")
            return False
    
    def health_check(self) -> dict:
        """Perform connection pool health check"""
        try:
            if not self.engine:
                return {'status': 'error', 'message': 'Engine not initialized'}
            
            # Test connection
            with self.engine.connect() as conn:
                result = conn.execute("SELECT 1").fetchone()
                if result[0] != 1:
                    return {'status': 'error', 'message': 'Database query failed'}
            
            # Get pool status
            pool_status = self.get_pool_status()
            
            # Check for pool exhaustion
            if pool_status['utilization_percent'] > 90:
                return {
                    'status': 'warning',
                    'message': 'High pool utilization',
                    'pool_status': pool_status
                }
            
            return {
                'status': 'healthy',
                'message': 'Connection pool is healthy',
                'pool_status': pool_status
            }
            
        except Exception as e:
            logger.error(f"Pool health check error: {e}")
            return {'status': 'error', 'message': str(e)}

# Global connection pool manager
connection_pool_manager = ConnectionPoolManager()

# Factory function for database sessions
def create_optimized_session():
    """Create optimized database session"""
    if not connection_pool_manager.engine:
        connection_pool_manager.create_engine()
    
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=connection_pool_manager.engine)
    return SessionLocal()

# Connection pool monitoring endpoint data
def get_connection_pool_metrics() -> dict:
    """Get connection pool metrics for monitoring"""
    try:
        pool_status = connection_pool_manager.get_pool_status()
        health_status = connection_pool_manager.health_check()
        
        return {
            'pool_status': pool_status,
            'health_status': health_status,
            'config': connection_pool_manager.pool_config,
            'timestamp': time.time()
        }
    except Exception as e:
        logger.error(f"Connection pool metrics error: {e}")
        return {'error': str(e)}

# Auto-scaling pool configuration
class AutoScalingPool:
    """
    Auto-scaling connection pool for dynamic load management
    """
    
    def __init__(self, base_pool_size: int = 20, max_pool_size: int = 100):
        self.base_pool_size = base_pool_size
        self.max_pool_size = max_pool_size
        self.current_pool_size = base_pool_size
        self.scale_up_threshold = 0.8  # Scale up when 80% utilized
        self.scale_down_threshold = 0.3  # Scale down when 30% utilized
    
    def should_scale_up(self, utilization: float) -> bool:
        """Check if pool should scale up"""
        return utilization > self.scale_up_threshold and self.current_pool_size < self.max_pool_size
    
    def should_scale_down(self, utilization: float) -> bool:
        """Check if pool should scale down"""
        return utilization < self.scale_down_threshold and self.current_pool_size > self.base_pool_size
    
    def get_optimal_pool_size(self, current_utilization: float) -> int:
        """Calculate optimal pool size based on current utilization"""
        if self.should_scale_up(current_utilization):
            return min(self.current_pool_size + 10, self.max_pool_size)
        elif self.should_scale_down(current_utilization):
            return max(self.current_pool_size - 5, self.base_pool_size)
        else:
            return self.current_pool_size

