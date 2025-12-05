# FreightOps Pro - Build and Run Commands

## Project Structure

```
FOPS/
├── frontend/           ← React + Vite + TypeScript
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
│
└── fopsbackend/        ← FastAPI + Python + Poetry
    ├── app/
    │   ├── main.py     ← FastAPI app instance (app.main:app)
    │   ├── routers/
    │   ├── models/
    │   ├── schemas/
    │   └── services/
    ├── pyproject.toml
    └── poetry.lock
```

**⚠️ IMPORTANT**: Backend was moved out of frontend directory to eliminate coupling.

---

## Frontend (React + Vite)

### Local Development

```bash
# Navigate to frontend
cd c:\Users\rcarb\Downloads\FOPS\frontend

# Install dependencies
npm install

# Run development server (http://localhost:5173)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Railway Deployment

**Repository**: https://github.com/freightops-pro/fopsfrontend.git

**Configuration**: [frontend/railway.json](../frontend/railway.json)

```json
{
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "npm install && npm run build"
  },
  "deploy": {
    "startCommand": "npx serve -s dist -l $PORT"
  }
}
```

**Environment Variables** (set in Railway dashboard):
```bash
NODE_ENV=production
VITE_ENVIRONMENT=production
VITE_API_BASE_URL=https://your-backend.railway.app/api
```

**Build Process**:
1. Install dependencies: `npm install`
2. Build Vite app: `npm run build` (outputs to `dist/`)
3. Serve static files: `npx serve -s dist -l $PORT`

---

## Backend (FastAPI + Python)

### Local Development

```bash
# Navigate to backend
cd c:\Users\rcarb\Downloads\FOPS\fopsbackend

# Install dependencies
poetry install

# Run development server with auto-reload (http://127.0.0.1:8000)
poetry run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Or use the PowerShell script
./start-backend.ps1
```

**API Documentation** (when running):
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### Production Server

```bash
# Run with gunicorn (production-ready ASGI server)
gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

### Railway Deployment

**Repository**: https://github.com/freightops-pro/fopsbackend.git

**Configuration**: [fopsbackend/railway.json](../fopsbackend/railway.json)

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120 --access-logfile - --error-logfile -"
  }
}
```

**Critical Files**:
- `runtime.txt` - Specifies Python 3.11.9
- `pyproject.toml` - Poetry dependencies
- `poetry.lock` - Locked dependency versions

**Build-Time Environment Variable** (⚠️ SET THIS FIRST):
```bash
NIXPACKS_POETRY_VERSION=1.8.5
```

**Runtime Environment Variables** (see [RAILWAY_ENV_COMPLETE_SETUP.txt](../fopsbackend/RAILWAY_ENV_COMPLETE_SETUP.txt)):
```bash
# Database (IMPORTANT: Use postgresql+psycopg:// for async driver)
DATABASE_URL=postgresql+psycopg://user:password@host/database?sslmode=require

# Security Keys
JWT_SECRET_KEY=<generated-key>
ENCRYPTION_KEY=<generated-key>
SSN_ENCRYPTION_KEY=<generated-key>

# Environment
ENVIRONMENT=production
DEBUG=False
PYTHONUNBUFFERED=1

# CORS
FRONTEND_URL=https://your-frontend.railway.app
BACKEND_URL=https://your-backend.railway.app
CORS_ORIGINS=https://your-frontend.railway.app

# (See full list in RAILWAY_ENV_COMPLETE_SETUP.txt)
```

**Build Process** (automatic via Nixpacks):
1. Detect Python 3.11.9 from `runtime.txt`
2. Install Poetry 1.8.5 (using `$NIXPACKS_POETRY_VERSION`)
3. Install dependencies: `poetry install --only main --no-interaction --no-ansi`
4. Start with gunicorn command

---

## Running Full Stack Locally

### Terminal 1 - Backend
```bash
cd c:\Users\rcarb\Downloads\FOPS\fopsbackend
poetry install
poetry run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal 2 - Frontend
```bash
cd c:\Users\rcarb\Downloads\FOPS\frontend
npm install
npm run dev
```

**URLs**:
- Frontend: http://localhost:5173
- Backend API: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs

The frontend is configured to connect to `http://127.0.0.1:8000/api` in development mode (see [src/lib/api-client.ts](../frontend/src/lib/api-client.ts)).

---

## Database Migrations (Backend)

```bash
cd c:\Users\rcarb\Downloads\FOPS\fopsbackend

# Create a new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1

# View migration history
poetry run alembic history
```

---

## Deployment Checklist

### Frontend Deployment
- [ ] Push code to https://github.com/freightops-pro/fopsfrontend.git
- [ ] Set environment variables in Railway (NODE_ENV, VITE_API_BASE_URL, etc.)
- [ ] Verify build succeeds
- [ ] Test static file serving

### Backend Deployment
- [ ] Push code to https://github.com/freightops-pro/fopsbackend.git
- [ ] **CRITICAL**: Set `NIXPACKS_POETRY_VERSION=1.8.5` in Railway Variables
- [ ] Set all runtime environment variables (DATABASE_URL, JWT_SECRET_KEY, etc.)
- [ ] Verify build succeeds
- [ ] Verify app starts successfully
- [ ] Run database migrations if needed
- [ ] Test API endpoints

### Post-Deployment
- [ ] Update CORS_ORIGINS in backend with frontend URL
- [ ] Update VITE_API_BASE_URL in frontend with backend URL
- [ ] Test authentication flow
- [ ] Verify WebSocket connections
- [ ] Test file uploads
- [ ] Verify third-party integrations (Haulpay, QuickBooks, etc.)

---

## Troubleshooting

### Backend Build Fails with "poetry==" Error
**Problem**: Nixpacks tries to install Poetry with empty version
**Solution**: Add `NIXPACKS_POETRY_VERSION=1.8.5` to Railway environment variables

### Backend Fails to Start - Database Connection Error
**Problem**: Missing DATABASE_URL or invalid connection string
**Solution**: Add Neon PostgreSQL connection string to Railway variables

### Frontend Can't Connect to Backend
**Problem**: CORS error or wrong API URL
**Solution**:
1. Check `VITE_API_BASE_URL` in frontend Railway variables
2. Check `CORS_ORIGINS` includes frontend URL in backend Railway variables

### Frontend Shows "pip: command not found" Error
**Problem**: Old backend_v2 directory was causing confusion
**Solution**: Already fixed - backend_v2 removed from frontend directory

---

## Key Module Paths

| Component | Path |
|-----------|------|
| FastAPI App Instance | `app.main:app` |
| Frontend Dev Server | `npm run dev` → Vite → http://localhost:5173 |
| Backend Dev Server | `poetry run uvicorn app.main:app --reload` → http://127.0.0.1:8000 |
| Frontend Prod Build | `npm run build` → `dist/` |
| Backend Prod Server | `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker` |

---

## Architecture Notes

- **Frontend-Backend Separation**: Completely decoupled - no static file serving from backend
- **Development**: Separate servers (Vite dev server + FastAPI with auto-reload)
- **Production**: Static files served by Railway/CDN + FastAPI served by gunicorn
- **Communication**: REST API + WebSockets
- **Authentication**: JWT tokens stored in localStorage
- **Database**: PostgreSQL (Neon for production, SQLite for local dev)
