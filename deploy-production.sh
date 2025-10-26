#!/bin/bash
# Production deployment script for FreightOps Backend with safety checks

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="freightops-backend"
CONTAINER_NAME="${APP_NAME}-container"
IMAGE_NAME="${APP_NAME}:latest"
HEALTH_CHECK_URL="http://localhost:8000/health"
MAX_RETRIES=5
RETRY_DELAY=10

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    # Check if .env file exists
    if [[ ! -f ".env" ]]; then
        log_error ".env file not found. Please create a .env file with production configuration."
        exit 1
    fi
    
    # Validate critical environment variables
    source .env
    if [[ -z "${SECRET_KEY:-}" ]] || [[ "${SECRET_KEY}" == "your-super-secret-key-change-this-in-production" ]]; then
        log_error "SECRET_KEY not properly configured for production."
        exit 1
    fi
    
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL not configured."
        exit 1
    fi
    
    if [[ "${ENVIRONMENT:-}" != "production" ]]; then
        log_warning "ENVIRONMENT is not set to 'production'. Current value: ${ENVIRONMENT:-unset}"
    fi
    
    log_success "Prerequisites check passed"
}

wait_for_health() {
    local url=$1
    local max_attempts=$2
    local delay=$3
    
    log_info "Waiting for health check at $url..."
    
    for ((i=1; i<=max_attempts; i++)); do
        if curl -f -s "$url" > /dev/null 2>&1; then
            log_success "Health check passed"
            return 0
        fi
        
        log_info "Health check attempt $i/$max_attempts failed, retrying in ${delay}s..."
        sleep $delay
    done
    
    log_error "Health check failed after $max_attempts attempts"
    return 1
}

cleanup_on_failure() {
    log_warning "Deployment failed. Cleaning up..."
    
    # Stop the new container if it's running
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        log_info "Stopping failed container..."
        docker stop "$CONTAINER_NAME" || true
        docker rm "$CONTAINER_NAME" || true
    fi
    
    # Try to restart the old container if it exists
    if docker images -q "$IMAGE_NAME" | grep -q .; then
        log_info "Attempting to restart previous version..."
        docker run -d \
          --name "$CONTAINER_NAME" \
          -p 8000:8000 \
          --env-file .env \
          --restart unless-stopped \
          "$IMAGE_NAME" || true
    fi
}

# Main deployment function
deploy() {
    log_info "Starting FreightOps Backend Deployment..."
    
    # Pre-deployment checks
    check_prerequisites
    
    # Backup current container (if running)
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        log_info "Backing up current deployment..."
        docker tag "$IMAGE_NAME" "${IMAGE_NAME}:backup-$(date +%Y%m%d-%H%M%S)" || true
    fi
    
    # Build new Docker image
    log_info "Building Docker image..."
    if ! docker build -t "$IMAGE_NAME" .; then
        log_error "Docker build failed"
        exit 1
    fi
    
    # Stop existing container
    log_info "Stopping existing container..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
    
    # Run new container
    log_info "Starting new container..."
    if ! docker run -d \
      --name "$CONTAINER_NAME" \
      -p 8000:8000 \
      --env-file .env \
      --restart unless-stopped \
      --health-cmd="curl -f http://localhost:8000/health || exit 1" \
      --health-interval=30s \
      --health-timeout=10s \
      --health-retries=3 \
      "$IMAGE_NAME"; then
        log_error "Failed to start new container"
        cleanup_on_failure
        exit 1
    fi
    
    # Wait for health check
    if ! wait_for_health "$HEALTH_CHECK_URL" $MAX_RETRIES $RETRY_DELAY; then
        log_error "New deployment failed health check"
        cleanup_on_failure
        exit 1
    fi
    
    # Run database migrations
    log_info "Running database migrations..."
    if ! docker exec "$CONTAINER_NAME" alembic upgrade head; then
        log_warning "Database migrations failed, but container is running"
        # Don't fail deployment for migration issues, but log them
    fi
    
    # Cleanup old images (keep last 3 versions)
    log_info "Cleaning up old Docker images..."
    docker images "$IMAGE_NAME" --format "table {{.Tag}}" | \
      grep -v "latest" | \
      tail -n +4 | \
      xargs -r docker rmi "$IMAGE_NAME":{} 2>/dev/null || true
    
    log_success "Deployment completed successfully!"
    log_info "Backend is available at http://localhost:8000"
    log_info "Health check: $HEALTH_CHECK_URL"
    log_info "API docs: http://localhost:8000/docs"
}

# Trap errors and cleanup
trap cleanup_on_failure ERR

# Run deployment
deploy

