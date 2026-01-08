from contextlib import asynccontextmanager
import logging
import sys
import os
import uuid

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Apply bcrypt patch for passlib compatibility BEFORE importing auth modules
import app.core  # noqa: F401 - triggers bcrypt patch

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import select

from app.api.router import api_router
from app.background.scheduler import shutdown_scheduler, start_scheduler, run_automation_cycle
from app.core.config import get_settings
from app.core.db import init_database, AsyncSessionFactory
from app.models.port import Port
from app.middleware.security import setup_security_middleware

# ========== ENHANCED LOGGING CONFIGURATION ==========
# Configure logging to properly separate stdout and stderr
# This helps container platforms correctly identify log levels

class InfoFilter(logging.Filter):
    """Filter to allow only INFO level messages."""
    def filter(self, record):
        return record.levelno <= logging.INFO

class ErrorFilter(logging.Filter):
    """Filter to allow only WARNING and ERROR level messages."""
    def filter(self, record):
        return record.levelno >= logging.WARNING

# Create formatters
info_formatter = logging.Formatter("%(levelname)s: %(message)s")
error_formatter = logging.Formatter("%(levelname)s: [PID:%(process)d] %(message)s")

# Create handlers
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
stdout_handler.addFilter(InfoFilter())
stdout_handler.setFormatter(info_formatter)

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.WARNING)
stderr_handler.addFilter(ErrorFilter())
stderr_handler.setFormatter(error_formatter)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[stdout_handler, stderr_handler]
)

# Reduce noise from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("alembic").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
settings = get_settings()
# ========== END LOGGING CONFIGURATION ==========


async def seed_ports():
    """Seed the database with major US ports if empty."""
    async with AsyncSessionFactory() as db:
        # Check if ports already exist
        result = await db.execute(select(Port).limit(1))
        if result.scalar_one_or_none():
            return  # Already seeded

        # Port authentication types:
        # - password: Username/password login to port portal (most common)
        # - oauth2: OAuth2 client credentials (Port Houston API)
        ports_data = [
            {
                "port_code": "USLAX",
                "port_name": "Port of Los Angeles",
                "unlocode": "USLAX",
                "region": "West Coast",
                "state": "CA",
                "country": "US",
                "services_supported": ["container_tracking", "vessel_schedule", "holds", "charges"],
                "adapter_class": "LALBAdapter",
                "auth_type": "password",  # pierPASS portal login
            },
            {
                "port_code": "USLGB",
                "port_name": "Port of Long Beach",
                "unlocode": "USLGB",
                "region": "West Coast",
                "state": "CA",
                "country": "US",
                "services_supported": ["container_tracking", "vessel_schedule", "holds", "charges"],
                "adapter_class": "LALBAdapter",
                "auth_type": "password",  # pierPASS portal login
            },
            {
                "port_code": "USNYC",
                "port_name": "Port of New York/New Jersey",
                "unlocode": "USNYC",
                "region": "East Coast",
                "state": "NJ",
                "country": "US",
                "services_supported": ["container_tracking", "vessel_schedule", "holds", "charges"],
                "adapter_class": "NYNJAdapter",
                "auth_type": "password",  # PNCT/APM portal login
            },
            {
                "port_code": "USSAV",
                "port_name": "Port of Savannah",
                "unlocode": "USSAV",
                "region": "East Coast",
                "state": "GA",
                "country": "US",
                "services_supported": ["container_tracking", "vessel_schedule", "holds", "charges"],
                "adapter_class": "SavannahAdapter",
                "auth_type": "password",  # GPA Pier1 portal login
            },
            {
                "port_code": "USHOU",
                "port_name": "Port of Houston",
                "unlocode": "USHOU",
                "region": "Gulf Coast",
                "state": "TX",
                "country": "US",
                "services_supported": ["container_tracking", "vessel_schedule", "holds", "charges"],
                "adapter_class": "PortHoustonAdapter",
                "auth_type": "password",  # portHOUSTON portal login
            },
            {
                "port_code": "USSEA",
                "port_name": "Port of Seattle",
                "unlocode": "USSEA",
                "region": "West Coast",
                "state": "WA",
                "country": "US",
                "services_supported": ["container_tracking", "vessel_schedule", "holds", "charges"],
                "adapter_class": "GenericPortAdapter",
                "auth_type": "password",  # NWSA portal login
            },
            {
                "port_code": "USOAK",
                "port_name": "Port of Oakland",
                "unlocode": "USOAK",
                "region": "West Coast",
                "state": "CA",
                "country": "US",
                "services_supported": ["container_tracking", "vessel_schedule", "holds", "charges"],
                "adapter_class": "GenericPortAdapter",
                "auth_type": "password",  # TraPac/SSA portal login
            },
            {
                "port_code": "USCHS",
                "port_name": "Port of Charleston",
                "unlocode": "USCHS",
                "region": "East Coast",
                "state": "SC",
                "country": "US",
                "services_supported": ["container_tracking", "vessel_schedule", "holds", "charges"],
                "adapter_class": "GenericPortAdapter",
                "auth_type": "password",  # SCPA portal login
            },
            {
                "port_code": "USNOR",
                "port_name": "Port of Norfolk",
                "unlocode": "USNOR",
                "region": "East Coast",
                "state": "VA",
                "country": "US",
                "services_supported": ["container_tracking", "vessel_schedule", "holds", "charges"],
                "adapter_class": "PortVirginiaAdapter",
                "auth_type": "password",  # VIG portal login
            },
            {
                "port_code": "USMIA",
                "port_name": "PortMiami",
                "unlocode": "USMIA",
                "region": "East Coast",
                "state": "FL",
                "country": "US",
                "services_supported": ["container_tracking", "vessel_schedule", "holds", "charges"],
                "adapter_class": "GenericPortAdapter",
                "auth_type": "password",  # POMTOC portal login
            },
        ]

        for port_data in ports_data:
            port = Port(
                id=str(uuid.uuid4()),
                **port_data,
                is_active="true",
            )
            db.add(port)

        await db.commit()


db_initialized = False
db_error: str | None = None

@asynccontextmanager
async def lifespan(_: FastAPI):
    global db_initialized, db_error
    import asyncio
    from app.core.db import test_database_connection, init_database

    async def initialize_database():
        """Initialize database in background."""
        global db_initialized, db_error
        try:
            db_connected = await test_database_connection()
            if not db_connected:
                db_error = "Database connection failed"
                logger.error(db_error)
                return

            await asyncio.wait_for(init_database(), timeout=30.0)

            try:
                await asyncio.wait_for(seed_ports(), timeout=10.0)
            except Exception as e:
                logger.warning(f"Port seeding optional step skipped: {e}")

            db_initialized = True
            logger.info("Database initialized and ready")

        except asyncio.TimeoutError:
            db_error = "Database initialization timed out"
            logger.error(db_error)
        except Exception as e:
            db_error = str(e)
            logger.error(f"Database initialization failed: {e}")

    asyncio.create_task(initialize_database())

    try:
        start_scheduler()
        logger.info("Background scheduler started")
    except Exception as e:
        logger.warning(f"Scheduler startup warning: {e}")

    try:
        from app.services.websocket_events import register_websocket_handlers
        register_websocket_handlers()
        logger.info("WebSocket handlers registered")
    except Exception as e:
        logger.warning(f"WebSocket handlers registration warning: {e}")

    async def run_automation_background():
        for _ in range(60):
            if db_initialized:
                break
            await asyncio.sleep(1)

        if not db_initialized:
            logger.warning("Skipping automation cycle - database not initialized")
            return

        try:
            await asyncio.wait_for(run_automation_cycle(), timeout=60.0)
            logger.info("Initial automation cycle completed")
        except Exception as e:
            logger.warning(f"Initial automation cycle optional step skipped: {e}")

    asyncio.create_task(run_automation_background())

    logger.info("Application startup complete")

    yield

    shutdown_scheduler()
    logger.info("Application shutdown initiated")


app = FastAPI(
    title=settings.project_name,
    debug=settings.debug,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Exception handlers to ensure CORS headers on errors
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with proper CORS headers."""
    origin = request.headers.get("origin")
    headers = {}
    if origin and origin in settings.backend_cors_origins:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with proper CORS headers."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    origin = request.headers.get("origin")
    headers = {}
    if origin and origin in settings.backend_cors_origins:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=headers,
    )


# Setup security middleware (rate limiting, security headers, audit logging)
setup_security_middleware(app)

app.include_router(api_router, prefix="/api")


@app.get("/templates/{entity_type}", tags=["Templates"])
async def download_public_template(entity_type: str) -> FileResponse:
    """
    Public endpoint for downloading CSV import templates.
    No authentication required since templates are just format examples.

    Supported entity types: drivers, equipment, loads
    """
    if entity_type not in ["drivers", "equipment", "loads"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type: {entity_type}. Must be one of: drivers, equipment, loads",
        )

    template_dir = Path(__file__).parent.parent / "templates"
    template_file = template_dir / f"{entity_type}_import_template.csv"

    if not template_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Template file not found for {entity_type}",
        )

    return FileResponse(
        path=template_file,
        media_type="text/csv",
        filename=f"{entity_type}_import_template.csv",
    )


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    logger.info("Root endpoint accessed")
    return {"status": "ok", "environment": settings.environment}

@app.get("/debug/cors", tags=["Debug"])
async def debug_cors() -> dict:
    """Debug endpoint to check CORS configuration."""
    logger.info("CORS debug endpoint accessed")
    return {
        "cors_origins": settings.backend_cors_origins,
        "cors_origins_raw": settings.cors_origins_raw,
        "cors_origins_env": os.environ.get("CORS_ORIGINS", "NOT SET"),
        "backend_cors_origins_env": os.environ.get("BACKEND_CORS_ORIGINS", "NOT SET"),
        "cors_origins_count": len(settings.backend_cors_origins),
    }

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint - responds immediately, reports database status."""
    logger.info("Health check endpoint accessed")
    return {
        "status": "ok",
        "service": "FreightOps API",
        "database_ready": db_initialized,
        "database_error": db_error
    }

@app.get("/ready", tags=["Health"])
async def readiness_check() -> dict:
    """Readiness check - only returns ok when database is ready."""
    from fastapi import HTTPException
    logger.info("Readiness check endpoint accessed")
    if not db_initialized:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "database_ready": False, "error": db_error}
        )
    return {"status": "ready", "database_ready": True}
