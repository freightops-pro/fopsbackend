"""
Health Check Tests
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.config.settings import settings

client = TestClient(app)

class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_health_check(self):
        """Test basic health check"""
        response = client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["environment"] == settings.ENVIRONMENT
    
    def test_liveness_check(self):
        """Test liveness check"""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data
    
    @patch('app.routes.health.get_db')
    def test_readiness_check_success(self, mock_get_db):
        """Test successful readiness check"""
        # Mock successful database connection
        mock_db = MagicMock()
        mock_db.execute.return_value = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["configuration"] == "ok"
    
    @patch('app.routes.health.get_db')
    def test_readiness_check_database_failure(self, mock_get_db):
        """Test readiness check with database failure"""
        # Mock database connection failure
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database connection failed")
        mock_get_db.return_value = mock_db
        
        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert "Service not ready" in data["detail"]
    
    @patch('app.config.settings.settings')
    def test_readiness_check_invalid_secret_key(self, mock_settings):
        """Test readiness check with invalid secret key in production"""
        mock_settings.SECRET_KEY = "your-super-secret-key-change-this-in-production"
        mock_settings.ENVIRONMENT = "production"
        
        with patch('app.routes.health.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.execute.return_value = MagicMock()
            mock_get_db.return_value = mock_db
            
            response = client.get("/health/ready")
            assert response.status_code == 503
    
    @patch('app.routes.health.get_db')
    def test_detailed_health_check(self, mock_get_db):
        """Test detailed health check"""
        mock_db = MagicMock()
        mock_db.execute.return_value = MagicMock()
        mock_get_db.return_value = mock_db
        
        response = client.get("/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "checks" in data
        assert "database" in data["checks"]
        assert "configuration" in data["checks"]
        assert "external_services" in data["checks"]
    
    @patch('app.routes.health.get_db')
    def test_detailed_health_check_database_failure(self, mock_get_db):
        """Test detailed health check with database failure"""
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database connection failed")
        mock_get_db.return_value = mock_db
        
        response = client.get("/health/detailed")
        assert response.status_code == 200  # Detailed check returns 200 even with failures
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"]["status"] == "unhealthy"









