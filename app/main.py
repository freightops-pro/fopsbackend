from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.router import api_router
from app.background.scheduler import shutdown_scheduler, start_scheduler, run_automation_cycle
from app.core.config import get_settings
from app.core.db import init_database, AsyncSessionFactory
from app.models.port import Port

settings = get_settings()


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
        print(f"Seeded {len(ports_data)} ports")


db_initialized = False
db_error: str | None = None

@asynccontextmanager
async def lifespan(_: FastAPI):
    global db_initialized, db_error
    print("[LIFESPAN] Starting application initialization...")
    import asyncio
    from app.core.db import test_database_connection, init_database
    
    async def initialize_database():
        """Initialize database in background - non-blocking for health checks."""
        global db_initialized, db_error
        try:
            # Step 1: Test database connection
            print("[LIFESPAN] Testing database connection...")
            db_connected = await test_database_connection()
            if not db_connected:
                db_error = "Database connection failed"
                print(f"[LIFESPAN] ERROR: {db_error}")
                return
            print("[LIFESPAN] Database connection successful")
            
            # Step 2: Initialize database tables
            print("[LIFESPAN] Initializing database tables...")
            await asyncio.wait_for(init_database(), timeout=30.0)
            print("[LIFESPAN] Database tables initialized successfully")
            
            # Step 3: Seed ports (optional - can fail)
            try:
                print("[LIFESPAN] Seeding ports...")
                await asyncio.wait_for(seed_ports(), timeout=10.0)
                print("[LIFESPAN] Ports seeded successfully")
            except asyncio.TimeoutError:
                print("[LIFESPAN] WARNING: Port seeding timed out after 10s - continuing anyway")
            except Exception as e:
                print(f"[LIFESPAN] WARNING: Error seeding ports: {e} - continuing anyway")
            
            db_initialized = True
            print("[LIFESPAN] Database initialization complete")
            
        except asyncio.TimeoutError:
            db_error = "Database initialization timed out after 30s"
            print(f"[LIFESPAN] ERROR: {db_error}")
        except Exception as e:
            db_error = str(e)
            print(f"[LIFESPAN] ERROR initializing database: {e}")
    
    # Start database initialization in background - DON'T BLOCK STARTUP
    # This allows health checks to respond while DB is still connecting
    asyncio.create_task(initialize_database())
    
    # Step 4: Start scheduler (can work without DB initially)
    try:
        print("[LIFESPAN] Starting scheduler...")
        start_scheduler()
        print("[LIFESPAN] Scheduler started")
    except Exception as e:
        print(f"[LIFESPAN] WARNING: Error starting scheduler: {e}")

    # Step 5: Register WebSocket event handlers
    try:
        print("[LIFESPAN] Registering WebSocket event handlers...")
        from app.services.websocket_events import register_websocket_handlers
        register_websocket_handlers()
        print("[LIFESPAN] WebSocket event handlers registered")
    except Exception as e:
        print(f"[LIFESPAN] WARNING: Error registering WebSocket handlers: {e}")

    # Step 6: Run initial automation cycle (optional - run in background after DB ready)
    async def run_automation_background():
        # Wait for database to be ready before running automation
        for _ in range(60):  # Wait up to 60 seconds
            if db_initialized:
                break
            await asyncio.sleep(1)
        
        if not db_initialized:
            print("[LIFESPAN] WARNING: Database not ready, skipping automation cycle")
            return
            
        try:
            print("[LIFESPAN] Running initial automation cycle...")
            await asyncio.wait_for(run_automation_cycle(), timeout=60.0)
            print("[LIFESPAN] Initial automation cycle completed")
        except asyncio.TimeoutError:
            print("[LIFESPAN] WARNING: Automation cycle timed out after 60s")
        except Exception as e:
            print(f"[LIFESPAN] WARNING: Error in automation cycle: {e}")
    
    # Start automation cycle in background - don't block startup
    asyncio.create_task(run_automation_background())
    
    print("[LIFESPAN] Application startup complete - ready to accept requests")
    
    yield
    
    print("[LIFESPAN] Shutting down...")
    shutdown_scheduler()
    print("[LIFESPAN] Shutdown complete")


app = FastAPI(
    title=settings.project_name,
    debug=settings.debug,
    lifespan=lifespan,
)

# Debug: Log CORS origins at startup
print(f"[CORS] Configured origins: {settings.backend_cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}

@app.get("/debug/cors", tags=["Debug"])
async def debug_cors() -> dict:
    """Debug endpoint to check CORS configuration."""
    import os
    return {
        "cors_origins": settings.backend_cors_origins,
        "cors_origins_env": os.environ.get("CORS_ORIGINS", "NOT SET"),
        "cors_origins_count": len(settings.backend_cors_origins),
    }

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint - responds immediately, reports database status."""
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
    if not db_initialized:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "database_ready": False, "error": db_error}
        )
    return {"status": "ready", "database_ready": True}

