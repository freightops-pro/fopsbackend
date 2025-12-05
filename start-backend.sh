#!/bin/bash
# FreightOps Backend Startup Script for Linux/Mac
# This script starts the FastAPI backend server

echo "Starting FreightOps Backend Server..."
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "WARNING: .env file not found!"
    echo "Please create a .env file with required configuration."
    echo "Required variables:"
    echo "  - DATABASE_URL (e.g., sqlite+aiosqlite:///./freightops.db)"
    echo ""
fi

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "ERROR: Poetry is not installed!"
    echo "Install Poetry from: https://python-poetry.org/docs/#installation"
    exit 1
fi

echo "Poetry found: $(poetry --version)"
echo ""

# Install dependencies if needed
echo "Checking dependencies..."
poetry install --no-interaction

# Start the server
echo ""
echo "Starting server on http://127.0.0.1:8000"
echo "API docs available at: http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

poetry run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000









