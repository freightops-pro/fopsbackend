# FreightOps Backend v2

This directory houses the greenfield rewrite of the FreightOps API. The goal is a clean,
modular FastAPI service that matches the new React 18 frontend while enforcing multi-tenant
isolation, modern authentication, and domain-driven boundaries.

## Project Layout

```
backend_v2/
├── pyproject.toml         # Poetry environment and dependencies
├── app/
│   ├── main.py            # FastAPI app factory and router wiring
│   ├── core/              # Settings, database, security primitives
│   ├── api/               # Shared dependencies and router registration
│   ├── models/            # SQLAlchemy ORM models
│   ├── schemas/           # Pydantic DTOs
│   ├── services/          # Domain services and business logic
│   └── routers/           # FastAPI routers per bounded context
├── alembic/               # Database migrations (env.py, versions/)
├── alembic.ini            # Alembic configuration
└── tests/                 # Pytest suites (coming soon)
```

## Getting Started

```bash
cd backend_v2
poetry install
poetry run uvicorn app.main:app --reload
```

### Database migrations

```bash
# Create a new migration after model changes
poetry run alembic revision --autogenerate -m "describe change"

# Apply migrations
poetry run alembic upgrade head
```

Environment variables can be defined in a `.env` file. See `app/core/config.py`
for the available settings (database URL, JWT secret, CORS configuration, etc.).

## Roadmap

1. Core auth + company context
2. Fleet safety & compliance APIs (driver, fuel/IFTA, automation)
3. Dispatch + load lifecycle
4. Accounting & settlements
5. Banking + Synctera
6. Collaboration + messenger

Each module will land with its own migrations, service layer coverage, and
integration tests to ensure regressions stay out of production.

