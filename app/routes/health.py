from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config.db import get_db
from app.config.settings import settings
import time
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health_check():
    """
    Basic health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0"
    }

@router.get("/db")
async def database_health(db: Session = Depends(get_db)):
    """
    Comprehensive database health check
    - Connection status
    - Query performance
    - Connection pool status
    """
    try:
        start_time = time.time()
        
        # Test basic connectivity
        result = db.execute(text("SELECT 1")).scalar()
        
        # Test query performance
        query_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Get connection pool info (if available)
        pool_info = {}
        try:
            pool = db.get_bind().pool
            pool_info = {
                "size": getattr(pool, 'size', 'unknown'),
                "checked_in": getattr(pool, 'checkedin', 'unknown'),
                "checked_out": getattr(pool, 'checkedout', 'unknown'),
                "overflow": getattr(pool, 'overflow', 'unknown'),
                "invalid": getattr(pool, 'invalid', 'unknown')
            }
        except Exception as e:
            logger.warning(f"Could not get pool info: {e}")
        
        # Test a more complex query
        start_complex = time.time()
        try:
            db.execute(text("SELECT COUNT(*) FROM companies LIMIT 1")).scalar()
            complex_query_time = (time.time() - start_complex) * 1000
        except Exception as e:
            logger.warning(f"Complex query test failed: {e}")
            complex_query_time = None
        
        health_status = "healthy"
        if query_time > 1000:  # If basic query takes more than 1 second
            health_status = "degraded"
        if query_time > 5000:  # If basic query takes more than 5 seconds
            health_status = "unhealthy"
        
        return {
            "status": health_status,
            "timestamp": time.time(),
            "response_time_ms": round(query_time, 2),
            "complex_query_time_ms": round(complex_query_time, 2) if complex_query_time else None,
            "connection_pool": pool_info,
            "database_url_configured": bool(settings.DATABASE_URL),
            "ssl_mode": settings.DB_SSL_MODE if hasattr(settings, 'DB_SSL_MODE') else 'not_configured'
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )

@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check including all system components
    """
    health_report = {
        "timestamp": time.time(),
        "overall_status": "healthy",
        "components": {}
    }
    
    # Database health
    try:
        db_start = time.time()
        db.execute(text("SELECT 1")).scalar()
        db_time = (time.time() - db_start) * 1000
        
        health_report["components"]["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_time, 2),
            "connection_pool": "configured"
        }
    except Exception as e:
        health_report["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_report["overall_status"] = "degraded"
    
    # Environment check
    health_report["components"]["environment"] = {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "debug_mode": settings.DEBUG,
        "database_url_configured": bool(settings.DATABASE_URL),
        "secret_key_configured": bool(settings.SECRET_KEY and settings.SECRET_KEY != "your-super-secret-key-change-this-in-production")
    }
    
    # External services check (basic connectivity)
    health_report["components"]["external_services"] = {
        "redis": "configured" if settings.REDIS_URL else "not_configured",
        "stripe": "configured" if settings.STRIPE_SECRET_KEY else "not_configured",
        "railsr": "configured" if settings.RAILSR_API_KEY else "not_configured",
        "gusto": "configured" if settings.GUSTO_CLIENT_ID else "not_configured"
    }
    
    return health_report

@router.get("/readiness")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Kubernetes-style readiness check
    Returns 200 if ready to serve traffic, 503 if not
    """
    try:
        # Test database connectivity
        db.execute(text("SELECT 1")).scalar()
        
        # Test that critical tables exist
        db.execute(text("SELECT COUNT(*) FROM companies LIMIT 1")).scalar()
        
        return {"status": "ready", "timestamp": time.time()}
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "error": str(e)}
        )

@router.get("/liveness")
async def liveness_check():
    """
    Kubernetes-style liveness check
    Always returns 200 if the application is running
    """
    return {"status": "alive", "timestamp": time.time()}