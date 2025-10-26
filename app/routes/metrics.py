from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.services.database_monitor import db_monitor
from app.middleware.performance_monitor import performance_monitor
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/")
async def get_metrics():
    """
    Get basic application metrics
    """
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "metrics_available": True
    }

@router.get("/performance")
async def get_performance_metrics():
    """
    Get performance metrics for all endpoints
    """
    try:
        metrics = performance_monitor.get_metrics()
        
        return {
            "status": "success",
            "timestamp": time.time(),
            "metrics": metrics,
            "summary": {
                "total_endpoints": len(metrics),
                "total_requests": sum(data["request_count"] for data in metrics.values()),
                "total_errors": sum(data["error_count"] for data in metrics.values()),
                "avg_response_time_ms": sum(data["avg_response_time_ms"] for data in metrics.values()) / len(metrics) if metrics else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }

@router.get("/database")
async def get_database_metrics(db: Session = Depends(get_db)):
    """
    Get database performance metrics
    """
    try:
        # Get database health report
        health_report = await db_monitor.get_full_health_report(db)
        
        return {
            "status": "success",
            "timestamp": time.time(),
            "database_metrics": health_report
        }
        
    except Exception as e:
        logger.error(f"Failed to get database metrics: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }

@router.get("/system")
async def get_system_metrics():
    """
    Get system-level metrics
    """
    import psutil
    import os
    
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get process metrics
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info()
        
        return {
            "status": "success",
            "timestamp": time.time(),
            "system_metrics": {
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "usage_percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "usage_percent": round((disk.used / disk.total) * 100, 2)
                },
                "process": {
                    "memory_mb": round(process_memory.rss / (1024**2), 2),
                    "cpu_percent": process.cpu_percent(),
                    "num_threads": process.num_threads(),
                    "create_time": process.create_time()
                }
            }
        }
        
    except ImportError:
        # psutil not available
        return {
            "status": "error",
            "error": "psutil not available for system metrics",
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }

@router.get("/prometheus")
async def get_prometheus_metrics():
    """
    Get metrics in Prometheus format
    """
    try:
        metrics = performance_monitor.get_metrics()
        
        # Format as Prometheus metrics
        prometheus_lines = []
        
        for key, data in metrics.items():
            # Request count
            prometheus_lines.append(
                f'http_requests_total{{method="{data["method"]}",path="{data["path"]}"}} {data["request_count"]}'
            )
            
            # Error count
            prometheus_lines.append(
                f'http_errors_total{{method="{data["method"]}",path="{data["path"]}"}} {data["error_count"]}'
            )
            
            # Average response time
            prometheus_lines.append(
                f'http_request_duration_ms_avg{{method="{data["method"]}",path="{data["path"]}"}} {data["avg_response_time_ms"]}'
            )
            
            # Max response time
            prometheus_lines.append(
                f'http_request_duration_ms_max{{method="{data["method"]}",path="{data["path"]}"}} {data["max_response_time_ms"]}'
            )
        
        # Add a comment header
        header = "# FreightOps Pro Performance Metrics\n"
        
        return Response(
            content=header + "\n".join(prometheus_lines),
            media_type="text/plain"
        )
        
    except Exception as e:
        logger.error(f"Failed to get Prometheus metrics: {e}")
        return Response(
            content=f"# Error: {str(e)}",
            media_type="text/plain",
            status_code=500
        )
