# FreightOps Backend v2

## Overview
FreightOps Backend is a FastAPI-based REST API for freight operations management. It provides multi-tenant SaaS functionality for trucking companies including fleet management, driver tracking, load dispatch, accounting, and integrations with industry services.

## Project Architecture

```
app/
├── main.py            # FastAPI application factory and router wiring
├── core/              # Settings, database, security primitives
│   ├── config.py      # Pydantic settings with environment variables
│   ├── db.py          # Async SQLAlchemy database configuration
│   └── security.py    # JWT authentication and password hashing
├── api/               # Shared dependencies and router registration
├── models/            # SQLAlchemy ORM models
├── schemas/           # Pydantic DTOs for request/response
├── services/          # Domain services and business logic
│   ├── motive/        # Motive ELD integration
│   ├── quickbooks/    # QuickBooks accounting integration
│   ├── samsara/       # Samsara fleet tracking
│   ├── wex/           # WEX fuel card integration
│   └── port/          # Port terminal integrations
├── routers/           # FastAPI routers per bounded context
├── background/        # Background jobs and scheduler
└── websocket/         # WebSocket hub for real-time collaboration
```

## Tech Stack
- **Framework**: FastAPI with Pydantic v2
- **Database**: PostgreSQL with async SQLAlchemy
- **Migrations**: Alembic
- **Authentication**: JWT tokens (python-jose)
- **Background Jobs**: APScheduler
- **Real-time**: WebSockets

## Running Locally

### Development Server
The application runs via the "Backend API" workflow on port 5000:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

### API Documentation
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Environment Variables

Required environment variables (set in Replit Secrets):
- `DATABASE_URL` - PostgreSQL connection string (auto-provided by Replit)
- `JWT_SECRET_KEY` - Secret key for JWT token signing
- `BACKEND_CORS_ORIGINS` - JSON array of allowed origins

Optional integrations:
- `GOOGLE_AI_API_KEY` - For AI OCR features
- `MOTIVE_API_KEY` - Motive ELD integration
- `QUICKBOOKS_CLIENT_ID/SECRET` - QuickBooks integration
- `SAMSARA_CLIENT_ID/SECRET` - Samsara integration

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Key API Endpoints

- `GET /` - Health check (status)
- `GET /health` - Simple health check
- `POST /api/auth/login` - User authentication
- `GET /api/dashboard/overview` - Dashboard data
- `GET /api/drivers` - Driver management
- `GET /api/loads` - Load/dispatch management
- `GET /api/equipment` - Fleet equipment
- `GET /api/accounting/*` - Accounting and settlements

## Recent Changes
- Converted DATABASE_URL to use async psycopg driver (`postgresql+psycopg://`)
- Fixed `asyncio.timeout` for Python 3.10 compatibility (using `asyncio.wait_for`)
- Added Dockerfile for Railway deployment (fixes Nixpacks build issues)
- Configured CORS for Replit proxy environment

## Deployment

### Replit
- Uses autoscale deployment with gunicorn + uvicorn workers
- Database: Replit PostgreSQL (Neon-backed)

### Railway
- Uses Dockerfile builder (not Nixpacks) to avoid psycopg build issues
- Requires `DATABASE_URL` and other environment variables to be set
