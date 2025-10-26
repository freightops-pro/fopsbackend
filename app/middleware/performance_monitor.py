"""
Performance Monitoring Middleware
"""
import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class PerformanceMonitor:
    """
    Performance monitoring and metrics collection
    """
    
    def __init__(self):
        self.request_times = {}
        self.error_counts = {}
        self.request_counts = {}
    
    def track_request(self, method: str, path: str, duration: float, status_code: int):
        """Track request performance metrics"""
        key = f"{method}:{path}"
        
        # Track request count
        if key not in self.request_counts:
            self.request_counts[key] = 0
        self.request_counts[key] += 1
        
        # Track request times
        if key not in self.request_times:
            self.request_times[key] = []
        self.request_times[key].append(duration)
        
        # Keep only last 100 requests per endpoint
        if len(self.request_times[key]) > 100:
            self.request_times[key] = self.request_times[key][-100:]
        
        # Track errors
        if status_code >= 400:
            if key not in self.error_counts:
                self.error_counts[key] = 0
            self.error_counts[key] += 1
    
    def get_metrics(self) -> dict:
        """Get current performance metrics"""
        metrics = {}
        
        for key in self.request_counts:
            method, path = key.split(":", 1)
            request_times = self.request_times.get(key, [])
            
            if request_times:
                avg_time = sum(request_times) / len(request_times)
                max_time = max(request_times)
                min_time = min(request_times)
            else:
                avg_time = max_time = min_time = 0
            
            metrics[key] = {
                "method": method,
                "path": path,
                "request_count": self.request_counts[key],
                "error_count": self.error_counts.get(key, 0),
                "avg_response_time_ms": round(avg_time * 1000, 2),
                "max_response_time_ms": round(max_time * 1000, 2),
                "min_response_time_ms": round(min_time * 1000, 2),
                "error_rate": round(
                    self.error_counts.get(key, 0) / self.request_counts[key] * 100, 2
                )
            }
        
        return metrics

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor request performance
    """
    
    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Track performance metrics
            performance_monitor.track_request(
                request.method,
                request.url.path,
                process_time,
                response.status_code
            )
            
            # Log slow requests
            if process_time > self.slow_request_threshold:
                logger.warning("Slow request detected", extra={
                    "extra_fields": {
                        "type": "slow_request",
                        "method": request.method,
                        "path": request.url.path,
                        "process_time_ms": round(process_time * 1000, 2),
                        "threshold_ms": self.slow_request_threshold * 1000,
                        "status_code": response.status_code
                    }
                })
            
            # Add performance headers
            response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            
            # Track failed request
            performance_monitor.track_request(
                request.method,
                request.url.path,
                process_time,
                500  # Internal server error
            )
            
            logger.error("Request failed during performance monitoring", extra={
                "extra_fields": {
                    "type": "failed_request",
                    "method": request.method,
                    "path": request.url.path,
                    "process_time_ms": round(process_time * 1000, 2),
                    "error": str(e)
                }
            })
            
            raise

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to expose performance metrics
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if this is a metrics request
        if request.url.path == "/metrics":
            metrics = performance_monitor.get_metrics()
            
            # Format as Prometheus-compatible metrics
            prometheus_metrics = []
            
            for key, data in metrics.items():
                # Request count
                prometheus_metrics.append(
                    f'http_requests_total{{method="{data["method"]}",path="{data["path"]}"}} {data["request_count"]}'
                )
                
                # Error count
                prometheus_metrics.append(
                    f'http_errors_total{{method="{data["method"]}",path="{data["path"]}"}} {data["error_count"]}'
                )
                
                # Average response time
                prometheus_metrics.append(
                    f'http_request_duration_ms_avg{{method="{data["method"]}",path="{data["path"]}"}} {data["avg_response_time_ms"]}'
                )
                
                # Max response time
                prometheus_metrics.append(
                    f'http_request_duration_ms_max{{method="{data["method"]}",path="{data["path"]}"}} {data["max_response_time_ms"]}'
                )
            
            return Response(
                content="\n".join(prometheus_metrics),
                media_type="text/plain"
            )
        
        # For non-metrics requests, just pass through
        return await call_next(request)

