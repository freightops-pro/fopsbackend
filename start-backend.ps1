# FreightOps Backend Startup Script for Windows
# This script starts the FastAPI backend server

Write-Host "Starting FreightOps Backend Server..." -ForegroundColor Green
Write-Host ""

# Check if .env file exists
if (-not (Test-Path .env)) {
    Write-Host "WARNING: .env file not found!" -ForegroundColor Yellow
    Write-Host "Please create a .env file with required configuration." -ForegroundColor Yellow
    Write-Host "Required variables:" -ForegroundColor Yellow
    Write-Host "  - DATABASE_URL (e.g., sqlite+aiosqlite:///./freightops.db)" -ForegroundColor Yellow
    Write-Host ""
}

# Check if Poetry is installed
try {
    $poetryVersion = poetry --version 2>&1
    Write-Host "Poetry found: $poetryVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Poetry is not installed!" -ForegroundColor Red
    Write-Host "Install Poetry from: https://python-poetry.org/docs/#installation" -ForegroundColor Yellow
    exit 1
}

# Install dependencies if needed
Write-Host "Checking dependencies..." -ForegroundColor Cyan
poetry install --no-interaction

# Start the server
Write-Host ""
Write-Host "Starting server on http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "API docs available at: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

poetry run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000









