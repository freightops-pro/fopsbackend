# FreightOps Platform Backend

A comprehensive FastAPI backend for the FreightOps Platform, providing RESTful APIs for freight management operations.

## Features

- **FastAPI Framework**: Modern, fast web framework for building APIs
- **SQLAlchemy ORM**: Database abstraction and management
- **JWT Authentication**: Secure token-based authentication
- **PostgreSQL Support**: Production-ready database
- **Alembic Migrations**: Database schema versioning
- **CORS Support**: Cross-origin resource sharing
- **Environment Configuration**: Flexible configuration management
- **API Documentation**: Automatic OpenAPI/Swagger documentation
- **OCR Processing**: Real document text extraction using Google Cloud Vision API

## Project Structure

```
backend/
├── app/
│   ├── config/
│   │   ├── __init__.py
│   │   ├── db.py          # Database configuration
│   │   └── settings.py    # Application settings
│   ├── controllers/
│   │   ├── __init__.py
│   │   └── userControllers.py  # Business logic
│   ├── models/
│   │   ├── __init__.py
│   │   └── userModels.py  # SQLAlchemy models
│   ├── routes/
│   │   ├── __init__.py
│   │   └── user.py        # API endpoints
│   └── main.py            # FastAPI application
├── alembic/               # Database migrations
├── requirements.txt       # Python dependencies
├── alembic.ini          # Alembic configuration
├── env.example          # Environment variables template
└── README.md           # This file
```

## Setup Instructions

### 1. Prerequisites

- Python 3.8+
- PostgreSQL database
- pip or conda package manager

### 2. Environment Setup

1. **Clone the repository** (if not already done)
2. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

3. **Create virtual environment**:
   ```bash
   python -m venv venv
   ```

4. **Activate virtual environment**:
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

5. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### 3. OCR Setup (Optional but Recommended)

For real document OCR processing, you have two options:

#### Option 1: Gemini API (RECOMMENDED - Easier Setup)

1. **Get API Key**:
   - Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Copy the key

2. **Set Environment Variable**:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```

3. **Test Setup**:
   ```bash
   python setup_google_cloud.py
   ```

#### Option 2: Google Cloud Vision API (More Complex Setup)

1. **Quick Setup Check**:
   ```bash
   python setup_google_cloud.py
   ```

2. **Manual Setup** (if needed):
   - Follow instructions in `GOOGLE_CLOUD_SETUP.md`
   - Copy `google_cloud.env.example` to `.env`
   - Add your Google Cloud credentials
   - Set environment variables:
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/key.json"
     export GOOGLE_CLOUD_PROJECT="your-project-id"
     ```

#### Fallback Mode (No API Keys Required):
   - OCR will work with intelligent mock data
   - Good for testing and development

### 4. Database Setup

1. **Create PostgreSQL database**:
   ```sql
   CREATE DATABASE freightops;
   ```

2. **Configure environment variables**:
   ```bash
   cp env.example .env
   ```
   Edit `.env` file with your database credentials and other settings.

3. **Initialize Alembic** (for migrations):
   ```bash
   alembic init alembic
   ```

4. **Create initial migration**:
   ```bash
   alembic revision --autogenerate -m "Initial migration"
   ```

5. **Apply migrations**:
   ```bash
   alembic upgrade head
   ```

### 4. Running the Application

#### Development Mode
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Production Mode
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 5. API Documentation

Once the server is running, you can access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Users
- `POST /api/v1/users/` - Create user
- `GET /api/v1/users/` - Get all users
- `GET /api/v1/users/{user_id}` - Get specific user
- `PUT /api/v1/users/{user_id}` - Update user
- `DELETE /api/v1/users/{user_id}` - Delete user

### Companies
- `POST /api/v1/companies/` - Create company
- `GET /api/v1/companies/` - Get all companies
- `GET /api/v1/companies/{company_id}` - Get specific company
- `PUT /api/v1/companies/{company_id}` - Update company
- `DELETE /api/v1/companies/{company_id}` - Delete company

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@localhost:5432/freightops` |
| `SECRET_KEY` | JWT secret key | `your-secret-key-here` |
| `ENVIRONMENT` | Environment (development/production) | `development` |
| `DEBUG` | Enable debug mode | `True` |
| `ALLOWED_ORIGINS` | CORS allowed origins | `http://localhost:3000,http://localhost:5173` |

## Development

### Code Formatting
```bash
black .
```

### Linting
```bash
flake8 .
```

### Running Tests
```bash
pytest
```

## Deployment

### Docker (Recommended)

1. **Create Dockerfile**:
   ```dockerfile
   FROM python:3.11-slim
   
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   
   COPY . .
   EXPOSE 8000
   
   CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
   ```

2. **Build and run**:
   ```bash
   docker build -t freightops-backend .
   docker run -p 8000:8000 freightops-backend
   ```

### Environment-Specific Configurations

- **Development**: Uses SQLite for simplicity
- **Production**: Uses PostgreSQL with proper connection pooling
- **Testing**: Uses in-memory SQLite database

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is part of the FreightOps Platform.
