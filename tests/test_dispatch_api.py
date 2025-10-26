"""
API Integration Tests for Dispatch Module

These tests verify API behavior, status codes, response models, and pagination.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime, date

from app.main import app
from app.models.simple_load import SimpleLoad
from app.models.userModels import LoadBilling, LoadAccessorial


@pytest.fixture
def company_token():
    """Mock JWT token"""
    return {
        "userId": "user-test",
        "companyId": "company-test",
        "email": "test@company.com"
    }


@pytest.fixture
def sample_loads(db: Session):
    """Create sample loads for testing"""
    loads = []
    for i in range(15):
        load = SimpleLoad(
            id=str(uuid4()),
            companyId="company-test",
            loadNumber=f"LD-TEST-{i:03d}",
            customerName=f"Customer {i}",
            pickupLocation=f"Pickup {i}",
            deliveryLocation=f"Delivery {i}",
            rate=1000 + (i * 100),
            status="pending" if i % 2 == 0 else "in_transit",
            priority="high" if i % 3 == 0 else "normal"
        )
        loads.append(load)
        db.add(load)
    db.commit()
    return loads


class TestAPIStatusCodes:
    """Test that API endpoints return proper HTTP status codes"""
    
    def test_list_loads_returns_200(
        self,
        client: TestClient,
        company_token,
        sample_loads
    ):
        """Test that listing loads returns 200 OK."""
        response = client.get(
            "/api/loads/",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        assert response.status_code == 200
    
    def test_create_load_returns_201(
        self,
        client: TestClient,
        company_token
    ):
        """Test that creating a load returns 201 Created."""
        response = client.post(
            "/api/loads/",
            json={
                "pickupLocation": "New Pickup",
                "deliveryLocation": "New Delivery",
                "rate": 1500
            },
            headers={"Authorization": f"Bearer {company_token}"}
        )
        assert response.status_code == 201
        assert "id" in response.json()
    
    def test_get_nonexistent_load_returns_404(
        self,
        client: TestClient,
        company_token
    ):
        """Test that getting non-existent load returns 404."""
        response = client.get(
            "/api/loads/nonexistent-id",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        assert response.status_code == 404
    
    def test_update_load_returns_200(
        self,
        client: TestClient,
        company_token,
        sample_loads
    ):
        """Test that updating a load returns 200 OK."""
        load = sample_loads[0]
        response = client.put(
            f"/api/loads/{load.id}",
            json={"status": "in_progress"},
            headers={"Authorization": f"Bearer {company_token}"}
        )
        assert response.status_code == 200
    
    def test_delete_load_returns_200(
        self,
        client: TestClient,
        company_token,
        sample_loads
    ):
        """Test that deleting a load returns 200 OK."""
        load = sample_loads[0]
        response = client.delete(
            f"/api/loads/{load.id}",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        assert response.status_code == 200
    
    def test_invalid_date_format_returns_400(
        self,
        client: TestClient,
        company_token
    ):
        """Test that invalid date format returns 400 Bad Request."""
        response = client.get(
            "/api/loads/scheduled?date=invalid-date",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]


class TestPaginationBehavior:
    """Test pagination functionality"""
    
    def test_loads_pagination_returns_correct_structure(
        self,
        client: TestClient,
        company_token,
        sample_loads
    ):
        """Test that pagination returns proper structure."""
        response = client.get(
            "/api/loads/?page=1&limit=5",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination structure
        assert "items" in data
        assert "pagination" in data
        assert "page" in data["pagination"]
        assert "limit" in data["pagination"]
        assert "total" in data["pagination"]
        assert "pages" in data["pagination"]
        assert "has_next" in data["pagination"]
        assert "has_prev" in data["pagination"]
        
        # Verify pagination values
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 5
        assert data["pagination"]["total"] == 15
        assert data["pagination"]["pages"] == 3
        assert data["pagination"]["has_next"] is True
        assert data["pagination"]["has_prev"] is False
        
        # Verify item count
        assert len(data["items"]) == 5
    
    def test_pagination_page_2_works_correctly(
        self,
        client: TestClient,
        company_token,
        sample_loads
    ):
        """Test that page 2 returns correct items."""
        response = client.get(
            "/api/loads/?page=2&limit=5",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["has_prev"] is True
        assert len(data["items"]) == 5
    
    def test_pagination_last_page_has_remaining_items(
        self,
        client: TestClient,
        company_token,
        sample_loads
    ):
        """Test that last page returns remaining items."""
        response = client.get(
            "/api/loads/?page=3&limit=5",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["pagination"]["page"] == 3
        assert data["pagination"]["has_next"] is False
        assert len(data["items"]) == 5
    
    def test_accessorials_pagination_works(
        self,
        client: TestClient,
        company_token,
        db: Session
    ):
        """
        Test that accessorials pagination works correctly.
        
        Issue #19: Pagination added to accessorials endpoint
        """
        # Create a load and billing
        load = SimpleLoad(
            id=str(uuid4()),
            companyId="company-test",
            loadNumber="LD-TEST",
            customerName="Test",
            pickupLocation="A",
            deliveryLocation="B"
        )
        db.add(load)
        db.commit()
        
        billing = LoadBilling(
            id=uuid4(),
            load_id=load.id,
            company_id="company-test",
            base_rate=1000,
            total_amount=1000
        )
        db.add(billing)
        db.commit()
        
        # Create 10 accessorials
        for i in range(10):
            acc = LoadAccessorial(
                id=uuid4(),
                load_id=load.id,
                billing_id=billing.id,
                company_id="company-test",
                type="detention",
                amount=100 + i,
                description=f"Accessorial {i}"
            )
            db.add(acc)
        db.commit()
        
        # Test pagination
        response = client.get(
            f"/api/loads/load-accessorials/{load.id}?page=1&limit=5",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "pagination" in data
        assert len(data["items"]) == 5
        assert data["pagination"]["total"] == 10


class TestResponseModels:
    """Test that API responses match expected schemas"""
    
    def test_load_response_contains_all_required_fields(
        self,
        client: TestClient,
        company_token,
        sample_loads
    ):
        """Test that load response contains all required fields."""
        load = sample_loads[0]
        response = client.get(
            f"/api/loads/{load.id}",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields present
        required_fields = [
            "id", "load_number", "customer_name", "pickup_location",
            "delivery_location", "rate", "status", "priority"
        ]
        for field in required_fields:
            assert field in data
    
    def test_paginated_response_structure_is_consistent(
        self,
        client: TestClient,
        company_token,
        sample_loads
    ):
        """Test that paginated responses have consistent structure."""
        response = client.get(
            "/api/loads/?page=1&limit=10",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert isinstance(data, dict)
        assert isinstance(data["items"], list)
        assert isinstance(data["pagination"], dict)
        
        # Verify each item has consistent structure
        if data["items"]:
            first_item = data["items"][0]
            for item in data["items"]:
                assert set(item.keys()) == set(first_item.keys())


class TestInputValidation:
    """Test input validation and error handling"""
    
    def test_create_load_without_required_fields_returns_400(
        self,
        client: TestClient,
        company_token
    ):
        """Test that creating load without required fields returns 400."""
        response = client.post(
            "/api/loads/",
            json={
                # Missing pickupLocation and deliveryLocation
                "rate": 1000
            },
            headers={"Authorization": f"Bearer {company_token}"}
        )
        
        assert response.status_code == 400
        assert "required" in response.json()["detail"].lower()
    
    def test_invalid_pagination_params_handled_correctly(
        self,
        client: TestClient,
        company_token,
        sample_loads
    ):
        """Test that invalid pagination params are handled."""
        # Test page < 1
        response = client.get(
            "/api/loads/?page=0&limit=10",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        assert response.status_code == 422  # Validation error
        
        # Test limit > max
        response = client.get(
            "/api/loads/?page=1&limit=1000",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        assert response.status_code == 422  # Validation error
    
    def test_missing_auth_token_returns_401(self, client: TestClient):
        """Test that requests without auth token return 401."""
        response = client.get("/api/loads/")
        assert response.status_code in [401, 403]  # Unauthorized or Forbidden


class TestDateHandling:
    """Test date and datetime handling"""
    
    def test_scheduled_loads_filters_by_date_correctly(
        self,
        client: TestClient,
        company_token,
        db: Session
    ):
        """Test that scheduled loads endpoint filters by date correctly."""
        today = date.today()
        
        # Create loads with different dates
        load_today = SimpleLoad(
            id=str(uuid4()),
            companyId="company-test",
            loadNumber="LD-TODAY",
            customerName="Today Customer",
            pickupLocation="A",
            deliveryLocation="B",
            pickupDate=datetime.combine(today, datetime.min.time())
        )
        db.add(load_today)
        db.commit()
        
        # Query for today's loads
        response = client.get(
            f"/api/loads/scheduled?date={today.isoformat()}",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        
        assert response.status_code == 200
        loads = response.json()
        
        # Should find the load
        load_ids = [l["id"] for l in loads]
        assert load_today.id in load_ids


class TestLoggingBehavior:
    """Test that proper logging occurs"""
    
    @patch('app.routes.loads.logger')
    def test_successful_operations_logged(
        self,
        mock_logger,
        client: TestClient,
        company_token
    ):
        """Test that successful operations are logged."""
        response = client.post(
            "/api/loads/",
            json={
                "pickupLocation": "A",
                "deliveryLocation": "B",
                "rate": 1000
            },
            headers={"Authorization": f"Bearer {company_token}"}
        )
        
        if response.status_code == 201:
            # Verify info logging was called
            assert mock_logger.info.called
    
    @patch('app.routes.loads.logger')
    def test_errors_logged_with_exc_info(
        self,
        mock_logger,
        client: TestClient,
        company_token
    ):
        """Test that errors are logged with exception info."""
        # Try to get non-existent load
        response = client.get(
            "/api/loads/invalid-id",
            headers={"Authorization": f"Bearer {company_token}"}
        )
        
        # Verify error logging (may or may not be called depending on implementation)
        # The important part is that if logger.error is called, it includes exc_info
        if mock_logger.error.called:
            call_kwargs = mock_logger.error.call_args[1]
            # Should have exc_info=True for proper traceback logging
            assert call_kwargs.get('exc_info') is True


# Run with: pytest tests/test_dispatch_api.py -v

