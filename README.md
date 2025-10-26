# FreightOps Pro - Backend API

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Private-red.svg)]()

Production-ready multi-tenant SaaS backend for transportation and logistics companies.

## 🚀 Tech Stack

- **Framework:** FastAPI (Python 3.8+)
- **Database:** PostgreSQL with SQLAlchemy ORM
- **Migrations:** Alembic
- **Authentication:** JWT tokens with bcrypt
- **Deployment:** Docker + Gunicorn
- **API Docs:** Auto-generated OpenAPI/Swagger

## 📋 Features

### Core Modules
- ✅ **Fleet Management** - Vehicles, drivers, assignments, compliance
- ✅ **Dispatch System** - Load management, scheduling, routing
- ✅ **Accounting** - Invoicing, settlements, financial reports
- ✅ **HR & Payroll** - Employee management, Gusto integration
- ✅ **Banking** - Railsr/Synctera integration for embedded banking
- ✅ **HQ Administration** - Multi-tenant management, billing

### Advanced Features
- 🔐 Multi-tenant architecture with company isolation
- 🤖 AI Services (Alex, Annie, Atlas)
- 📊 Real-time WebSocket support
- 🔌 Port integrations (LA, Long Beach, Houston, NY, Savannah)
- 📧 Email notifications
- 🔍 Advanced OCR with Google Cloud Vision
- 💳 Stripe subscription management
- 📦 Multi-leg load coordination
- 🌍 Multi-location & multi-authority support

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher
- PostgreSQL 12+
- Redis (optional, for caching)

### Setup

1. **Clone the repository:**
```bash
git clone https://github.com/freightops-pro/fopsbackend.git
cd fopsbackend
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables:**
```bash
cp env.example .env
# Edit .env with your configuration
```

5. **Run database migrations:**
```bash
alembic upgrade head
```

6. **Start the development server:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 🔧 Environment Variables

Create a `.env` file with the following variables:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/freightops

# JWT Authentication
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Google Cloud (OCR)
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_CREDENTIALS=path/to/credentials.json

# Email (SendGrid)
SENDGRID_API_KEY=SG.xxx
FROM_EMAIL=noreply@freightopspro.com

# Gusto (HR/Payroll)
GUSTO_CLIENT_ID=xxx
GUSTO_CLIENT_SECRET=xxx

# Railsr (Banking)
RAILSR_API_KEY=xxx
RAILSR_BASE_URL=https://api.railsr.com
```

## 📚 API Documentation

Once the server is running, access:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## 🗄️ Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## 🏗️ Project Structure

```
backend/
├── alembic/              # Database migrations
├── app/
│   ├── adapters/         # Port integrations
│   ├── config/           # Configuration & settings
│   ├── middleware/       # Rate limiting, logging, etc.
│   ├── models/           # SQLAlchemy models
│   ├── routes/           # API endpoints
│   ├── schema/           # Pydantic schemas
│   ├── services/         # Business logic
│   ├── websocket/        # WebSocket managers
│   └── main.py           # FastAPI application
├── scripts/              # Utility scripts
├── tests/                # Test suite
├── requirements.txt      # Python dependencies
└── README.md
```

## 🔐 Authentication

All protected endpoints require a JWT token in the Authorization header:

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/fleet/vehicles
```

### Login
```bash
POST /api/auth/login
{
  "username": "user@example.com",
  "password": "password"
}
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py
```

## 🐳 Docker Deployment

```bash
# Build image
docker build -t freightops-backend .

# Run container
docker-compose up -d

# View logs
docker-compose logs -f
```

## 📊 Database Schema

### Key Tables
- `companies` - Multi-tenant company records
- `users` - User accounts with role-based access
- `vehicles` - Trucks, trailers, equipment
- `drivers` - Driver profiles and compliance
- `simple_loads` - Load/shipment records
- `invoices` - Financial invoicing
- `employees` - HR employee records
- `subscription_plans` - Stripe subscription tiers

## 🔌 API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - Company registration
- `POST /api/auth/refresh` - Refresh token

### Fleet Management
- `GET /api/fleet/vehicles` - List vehicles
- `POST /api/fleet/vehicles` - Create vehicle
- `GET /api/fleet/drivers` - List drivers
- `POST /api/fleet/drivers` - Create driver

### Dispatch
- `GET /api/loads` - List loads
- `POST /api/loads` - Create load
- `PATCH /api/loads/{id}` - Update load
- `POST /api/loads/{id}/assign` - Assign truck

### Accounting
- `GET /api/invoices` - List invoices
- `POST /api/invoices` - Create invoice
- `GET /api/settlements` - Driver settlements

### HQ Admin
- `GET /api/hq/companies` - List tenants
- `POST /api/hq/companies` - Create tenant
- `GET /api/hq/analytics` - Platform analytics

## 🤝 Contributing

This is a private repository. Contact the development team for contribution guidelines.

## 📝 License

Proprietary - All rights reserved

## 👥 Support

For support, email: support@freightopspro.com

## 🚦 Status

- **Production Ready:** 85%
- **Active Development:** Yes
- **Latest Version:** 1.0.0

---

Built with ❤️ by the FreightOps Pro Team
