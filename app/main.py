import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.config.settings import settings
from sqlalchemy import text
from app.config.db import create_tables, engine
from app import models  # noqa: F401 - ensure models are imported for table creation
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.middleware.validation import InputValidationMiddleware
from app.config.logging_config import setup_logging, get_logger
from app.routes import user, employee
from app.routes import equipment
from app.routes import customers as customers_module
from app.routes import vendors as vendors_module
from app.routes import documents as documents_module
from app.routes import bills as bills_module
from app.routes import invoices as invoices_module
from app.routes import companies as companies_module
from app.routes import onboarding
from app.routes import payroll
from app.routes import benefits
from app.routes import hr_dashboard
from app.routes import loads as loads_router
from app.routes import maintenance as maintenance_router
from app.routes import compliance as compliance_router
from app.routes import banking as banking_router
from app.routes import hq as hq_router
from app.routes import chat as chat_router
from app.routes import settlements as settlements_router
from app.routes import delivery as delivery_router
from app.routes import pickup as pickup_router
from app.routes import truck_assignment as truck_assignment_router
from app.routes import driver_auth as driver_auth_router
from app.routes import hq_auth as hq_auth_router
from app.routes import subscriptions as subscriptions_router
from app.routes import ocr as ocr_router
# from app.routes import team_messaging
from app.routes import health as health_router
from app.routes import ports as ports_router
from app.routes import metrics as metrics_router
from app.routes import api_keys as api_keys_router
from app.routes import multi_leg
from app.routes import enterprise
from app.routes import collaboration
from app.routes import multi_location
from app.routes import driver_websocket
from app.routes import performance
from app.routes import company_management
from app.routes import load_board
from app.routes import commission
from app.routes import dashboard
from app.routes import automated_dispatch
from app.routes import annie_ai
from app.routes import alex_ai
from app.routes import atlas_ai
from app.routes import transload
from app.routes import routing
from app.routes import filters
from app.routes import containers
from app.routes import multi_authority
from app.middleware.request_logging import RequestLoggingMiddleware, PerformanceMiddleware
from app.middleware.error_tracker import ErrorTrackingMiddleware, DatabaseErrorMiddleware
from app.middleware.performance_monitor import PerformanceMonitoringMiddleware

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logging first
    setup_logging()
    logger = get_logger(__name__)
    
    # Startup
    logger.info("Starting FreightOps API", extra={
        "extra_fields": {
            "environment": settings.ENVIRONMENT,
            "debug_mode": settings.DEBUG
        }
    })
    create_tables()
    logger.info("Database tables created successfully")
    # Ensure simple_loads.meta JSON column exists (idempotent for Postgres/SQLite)
    try:
        with engine.connect() as conn:
            dialect = engine.dialect.name
            if dialect == "sqlite":
                # SQLite cannot ADD COLUMN with type JSON reliably across versions, use TEXT as fallback
                conn.execute(text("PRAGMA table_info(simple_loads)"))
                cols = conn.execute(text("PRAGMA table_info(simple_loads)")).fetchall()
                has_meta = any(row[1] == "meta" for row in cols)
                if not has_meta:
                    conn.execute(text("ALTER TABLE simple_loads ADD COLUMN meta JSON"))
            else:
                # Postgres
                conn.execute(text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='simple_loads' AND column_name='meta'
                        ) THEN
                            ALTER TABLE simple_loads ADD COLUMN meta JSONB;
                        END IF;
                    END$$;
                    """
                ))
            conn.commit()
    except Exception as e:
        logger.warning("Meta column ensure error (non-fatal)", extra={
            "extra_fields": {"error": str(e)}
        })
    
    logger.info("FreightOps API startup completed successfully")
    yield
    
    # Shutdown
    logger.info("Shutting down FreightOps API...")

# Create FastAPI instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="FreightOps Platform API - Comprehensive freight management system",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(Exception, rate_limit_exceeded_handler)

# Trusted host middleware for security (add before CORS)
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure with your domain in production
    )

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Add HSTS header in production
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    
    return response

# Input validation middleware
app.add_middleware(InputValidationMiddleware)

# Monitoring and observability middleware
app.add_middleware(ErrorTrackingMiddleware)
app.add_middleware(DatabaseErrorMiddleware)
app.add_middleware(PerformanceMonitoringMiddleware, slow_request_threshold=1.0)
app.add_middleware(RequestLoggingMiddleware)

# Advanced rate limiting for 5000+ users
from app.middleware.advanced_rate_limiter import AdvancedRateLimiterMiddleware
app.add_middleware(AdvancedRateLimiterMiddleware)

# CORS middleware - MUST BE LAST so it runs FIRST
# This handles preflight OPTIONS requests before other middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(user.router)
app.include_router(employee.router)
app.include_router(equipment.router)
app.include_router(customers_module.router)
app.include_router(vendors_module.router)
app.include_router(documents_module.router)
app.include_router(bills_module.router)
app.include_router(invoices_module.router)
app.include_router(companies_module.router)
app.include_router(onboarding.router)
app.include_router(payroll.router)
app.include_router(payroll.misc_router)
app.include_router(benefits.router)
app.include_router(hr_dashboard.router)
app.include_router(loads_router.router)
app.include_router(maintenance_router.router)
app.include_router(compliance_router.router)
app.include_router(banking_router.router)
app.include_router(hq_router.router)
app.include_router(chat_router.router)
app.include_router(settlements_router.router)
app.include_router(delivery_router.router)
app.include_router(pickup_router.router)
app.include_router(truck_assignment_router.router)
app.include_router(driver_auth_router.router)
app.include_router(hq_auth_router.router)
app.include_router(subscriptions_router.router)
app.include_router(ocr_router.router)
# app.include_router(team_messaging.router)
app.include_router(health_router.router)
app.include_router(ports_router.router)
app.include_router(metrics_router.router)
app.include_router(api_keys_router.router)

# New advanced features
app.include_router(multi_leg.router)
app.include_router(enterprise.router)
app.include_router(collaboration.router)
app.include_router(multi_location.router)
app.include_router(driver_websocket.router)
app.include_router(performance.router)
app.include_router(dashboard.router)
app.include_router(automated_dispatch.router)
app.include_router(transload.router)
app.include_router(routing.router)
app.include_router(filters.router)
app.include_router(containers.router)
app.include_router(multi_authority.router)
app.include_router(company_management.router)
app.include_router(load_board.router)
app.include_router(commission.router)

# AI Assistant routes (temporarily disabled)
app.include_router(annie_ai.router)
app.include_router(alex_ai.router)
app.include_router(atlas_ai.router)

# Performance-optimized routes for 5000+ users

# Mount static files for serving uploaded files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# Root endpoint
@app.get("/")
def api():
    return {
        "message": "Welcome to FreightOps Platform API",
        "docs": "/docs",
        "status": "healthy",
        "environment": settings.ENVIRONMENT
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )