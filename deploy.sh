#!/bin/bash

# FreightOps Backend Production Deployment Script

set -e  # Exit on any error

echo "🚀 Starting FreightOps Backend Deployment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy env.production.example to .env and configure it"
    exit 1
fi

# Load environment variables
source .env

# Check required environment variables
required_vars=("DATABASE_URL" "SECRET_KEY" "ENVIRONMENT")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: Required environment variable $var is not set"
        exit 1
    fi
done

echo "✅ Environment variables validated"

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "🗄️ Running database migrations..."
alembic upgrade head

# Create initial HQ admin (if not exists)
echo "👤 Creating initial HQ admin..."
python create_hq_admin.py

# Start the application
echo "🎯 Starting FreightOps Backend..."
if [ "$ENVIRONMENT" = "production" ]; then
    echo "Production mode: Starting with Gunicorn"
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
else
    echo "Development mode: Starting with Uvicorn"
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
