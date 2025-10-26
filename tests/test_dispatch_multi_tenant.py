"""
Multi-Tenant Isolation Tests for Dispatch Module

These tests verify that multi-tenant data isolation is properly enforced
in the dispatch module to prevent cross-tenant data access.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4

from app.main import app
from app.models.simple_load import SimpleLoad
from app.models.userModels import Users, Driver, LoadBilling, LoadAccessorial


@pytest.fixture
def company_a_token():
    """Mock JWT token for Company A"""
    return {
        "userId": "user-a-1",
        "companyId": "company-a",
        "email": "user@company-a.com"
    }


@pytest.fixture
def company_b_token():
    """Mock JWT token for Company B"""
    return {
        "userId": "user-b-1",
        "companyId": "company-b",
        "email": "user@company-b.com"
    }


@pytest.fixture
def company_a_load(db: Session):
    """Create a test load for Company A"""
    load = SimpleLoad(
        id=str(uuid4()),
        companyId="company-a",
        loadNumber="LD-COMPANY-A-001",
        customerName="Customer A",
        pickupLocation="Location A Pickup",
        deliveryLocation="Location A Delivery",
        rate=1000.00,
        status="pending"
    )
    db.add(load)
    db.commit()
    db.refresh(load)
    return load


@pytest.fixture
def company_b_load(db: Session):
    """Create a test load for Company B"""
    load = SimpleLoad(
        id=str(uuid4()),
        companyId="company-b",
        loadNumber="LD-COMPANY-B-001",
        customerName="Customer B",
        pickupLocation="Location B Pickup",
        deliveryLocation="Location B Delivery",
        rate=2000.00,
        status="pending"
    )
    db.add(load)
    db.commit()
    db.refresh(load)
    return load


class TestMultiTenantIsolation:
    """Test multi-tenant data isolation in dispatch endpoints"""
    
    def test_list_loads_returns_only_own_company_loads(
        self, 
        client: TestClient, 
        company_a_token, 
        company_a_load, 
        company_b_load
    ):
        """
        Test that listing loads returns only loads from the authenticated company.
        
        Security Issue #1: list_loads must filter by company_id
        """
        # Company A user should only see Company A loads
        response = client.get(
            "/api/loads/",
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have pagination metadata
        assert "items" in data
        assert "pagination" in data
        
        # All items must belong to Company A
        for item in data["items"]:
            assert item["company_id"] == "company-a"
            assert item["id"] != company_b_load.id
    
    def test_get_load_by_id_rejects_other_company_load(
        self,
        client: TestClient,
        company_a_token,
        company_b_load
    ):
        """
        Test that getting a load by ID fails if it belongs to another company.
        
        Security Issue #2: get_load must verify ownership
        """
        # Company A user tries to access Company B's load
        response = client.get(
            f"/api/loads/{company_b_load.id}",
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        # Should be 404, not 200
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_assign_load_rejects_other_company_load(
        self,
        client: TestClient,
        company_a_token,
        company_b_load
    ):
        """
        Test that assigning a load fails if it belongs to another company.
        
        Security Issue #4: assign_load must verify ownership
        """
        # Company A user tries to assign Company B's load
        response = client.post(
            f"/api/loads/{company_b_load.id}/assign",
            json={"driverId": "driver-123"},
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        # Should be 404, not 200
        assert response.status_code == 404
    
    def test_update_load_rejects_other_company_load(
        self,
        client: TestClient,
        company_a_token,
        company_b_load
    ):
        """
        Test that updating a load fails if it belongs to another company.
        
        Security Issue #5: update_load must verify ownership
        """
        # Company A user tries to update Company B's load
        response = client.put(
            f"/api/loads/{company_b_load.id}",
            json={"status": "cancelled"},
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        # Should be 404, not 200
        assert response.status_code == 404
    
    def test_delete_load_rejects_other_company_load(
        self,
        client: TestClient,
        company_a_token,
        company_b_load,
        db: Session
    ):
        """
        Test that deleting a load fails if it belongs to another company.
        
        Security Issue #6: delete_load must verify ownership
        """
        # Company A user tries to delete Company B's load
        response = client.delete(
            f"/api/loads/{company_b_load.id}",
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        # Should be 404, not 200
        assert response.status_code == 404
        
        # Verify load still exists in database
        load = db.query(SimpleLoad).filter(SimpleLoad.id == company_b_load.id).first()
        assert load is not None
    
    def test_get_load_billing_rejects_other_company_billing(
        self,
        client: TestClient,
        company_a_token,
        company_b_load,
        db: Session
    ):
        """
        Test that getting billing info fails for other company's loads.
        
        Security Issue #7: get_load_billing must verify ownership
        """
        # Create billing for Company B's load
        billing = LoadBilling(
            id=uuid4(),
            load_id=company_b_load.id,
            company_id="company-b",
            base_rate=2000.00,
            total_amount=2000.00,
            billing_status="pending",
            customer_name="Customer B"
        )
        db.add(billing)
        db.commit()
        
        # Company A user tries to access Company B's billing
        response = client.get(
            f"/api/loads/load-billing/{company_b_load.id}",
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        # Should be 404, not 200
        assert response.status_code == 404
    
    def test_get_load_accessorials_rejects_other_company_accessorials(
        self,
        client: TestClient,
        company_a_token,
        company_b_load,
        db: Session
    ):
        """
        Test that getting accessorials fails for other company's loads.
        
        Security Issue #8/9: get_load_accessorials must verify ownership
        """
        # Company A user tries to access Company B's accessorials
        response = client.get(
            f"/api/loads/load-accessorials/{company_b_load.id}",
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        # Should be 404, not 200
        assert response.status_code == 404
    
    def test_truck_assignment_rejects_other_company_load(
        self,
        client: TestClient,
        company_a_token,
        company_b_load
    ):
        """
        Test that truck assignment fails for other company's loads.
        """
        response = client.post(
            f"/api/truck-assignment/{company_b_load.id}/assign-truck",
            json={"truckId": "truck-123", "timestamp": "2025-01-26T12:00:00Z"},
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        # Should be 404 or 403
        assert response.status_code in [404, 403]
    
    def test_pickup_operations_reject_other_company_load(
        self,
        client: TestClient,
        company_a_token,
        company_b_load
    ):
        """
        Test that pickup operations fail for other company's loads.
        """
        # Test start navigation
        response = client.post(
            f"/api/pickup/{company_b_load.id}/start-navigation",
            json={"timestamp": "2025-01-26T12:00:00Z"},
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        assert response.status_code in [404, 403]
        
        # Test mark arrival
        response = client.post(
            f"/api/pickup/{company_b_load.id}/arrive",
            json={"timestamp": "2025-01-26T12:00:00Z"},
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        assert response.status_code in [404, 403]
    
    def test_delivery_operations_reject_other_company_load(
        self,
        client: TestClient,
        company_a_token,
        company_b_load
    ):
        """
        Test that delivery operations fail for other company's loads.
        """
        # Test mark arrival
        response = client.post(
            f"/api/delivery/{company_b_load.id}/arrive",
            json={"timestamp": "2025-01-26T12:00:00Z"},
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        assert response.status_code in [404, 403]
        
        # Test confirm delivery
        response = client.post(
            f"/api/delivery/{company_b_load.id}/confirm",
            json={
                "recipientName": "John Doe",
                "deliveryTimestamp": "2025-01-26T12:00:00Z"
            },
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        assert response.status_code in [404, 403]


class TestDataLeakagePrevention:
    """Test that data doesn't leak between tenants"""
    
    def test_scheduled_loads_filtered_by_company(
        self,
        client: TestClient,
        company_a_token,
        company_a_load,
        company_b_load,
        db: Session
    ):
        """
        Test that scheduled loads endpoint returns only company's loads.
        
        Security Issue #3: list_scheduled_loads must filter by company
        """
        # Set both loads to same date
        from datetime import date
        today = date.today()
        company_a_load.pickupDate = today
        company_b_load.pickupDate = today
        db.commit()
        
        # Company A user queries scheduled loads
        response = client.get(
            f"/api/loads/scheduled?date={today.isoformat()}",
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        assert response.status_code == 200
        loads = response.json()
        
        # Should only contain Company A's load
        load_ids = [l["id"] for l in loads]
        assert company_a_load.id in load_ids
        assert company_b_load.id not in load_ids
    
    def test_no_data_leakage_in_error_messages(
        self,
        client: TestClient,
        company_a_token,
        company_b_load
    ):
        """
        Test that error messages don't leak information about other company's data.
        """
        response = client.get(
            f"/api/loads/{company_b_load.id}",
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        # Error message should be generic
        assert response.status_code == 404
        error_detail = response.json()["detail"]
        
        # Should not contain company names, load details, etc.
        assert "company-b" not in error_detail.lower()
        assert company_b_load.customerName not in error_detail


class TestDriverAssignmentSecurity:
    """Test that driver assignment respects multi-tenancy"""
    
    def test_cannot_assign_other_company_driver_to_own_load(
        self,
        client: TestClient,
        company_a_token,
        company_a_load,
        db: Session
    ):
        """
        Test that assigning a driver from another company fails.
        """
        # Create a driver for Company B
        driver_b = Driver(
            id=str(uuid4()),
            companyId="company-b",
            firstName="Bob",
            lastName="Driver",
            status="available"
        )
        db.add(driver_b)
        db.commit()
        
        # Company A tries to assign Company B's driver
        response = client.post(
            f"/api/loads/{company_a_load.id}/assign",
            json={"driverId": driver_b.id},
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        # Should fail with 400 (driver not found in company)
        assert response.status_code == 400
        assert "different company" in response.json()["detail"].lower()


class TestPaginationSecurity:
    """Test that pagination doesn't leak cross-tenant data"""
    
    def test_load_accessorials_pagination_filtered_by_company(
        self,
        client: TestClient,
        company_a_token,
        company_a_load,
        company_b_load,
        db: Session
    ):
        """
        Test that paginated accessorials are filtered by company.
        
        Security Issue #19: Pagination must respect tenant boundaries
        """
        # Create accessorials for both companies
        billing_a = LoadBilling(
            id=uuid4(),
            load_id=company_a_load.id,
            company_id="company-a",
            base_rate=1000,
            total_amount=1000
        )
        billing_b = LoadBilling(
            id=uuid4(),
            load_id=company_b_load.id,
            company_id="company-b",
            base_rate=2000,
            total_amount=2000
        )
        db.add_all([billing_a, billing_b])
        db.commit()
        
        acc_a = LoadAccessorial(
            id=uuid4(),
            load_id=company_a_load.id,
            billing_id=billing_a.id,
            company_id="company-a",
            type="detention",
            amount=100
        )
        acc_b = LoadAccessorial(
            id=uuid4(),
            load_id=company_b_load.id,
            billing_id=billing_b.id,
            company_id="company-b",
            type="detention",
            amount=200
        )
        db.add_all([acc_a, acc_b])
        db.commit()
        
        # Company A queries accessorials
        response = client.get(
            f"/api/loads/load-accessorials/{company_a_load.id}?page=1&limit=10",
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have pagination
        assert "pagination" in data
        assert "items" in data
        
        # All items must belong to Company A
        for item in data["items"]:
            assert item["company_id"] == "company-a"


class TestServiceLayerSecurity:
    """Test that service layer enforces multi-tenant isolation"""
    
    def test_service_layer_rejects_cross_tenant_access(self, db: Session):
        """
        Test that service layer functions enforce company_id filtering.
        """
        from app.services.truck_assignment_service import get_truck_assignment_status
        from app.services.pickup_service import get_pickup_status
        from app.services.delivery_service import get_delivery_status
        
        # Create load for Company B
        load_b = SimpleLoad(
            id=str(uuid4()),
            companyId="company-b",
            loadNumber="LD-TEST",
            customerName="Test",
            pickupLocation="A",
            deliveryLocation="B"
        )
        db.add(load_b)
        db.commit()
        
        # Try to access with Company A's ID
        status = get_truck_assignment_status(db, load_b.id, "company-a")
        assert status is None  # Should not find it
        
        status = get_pickup_status(db, load_b.id, "company-a")
        assert status is None  # Should not find it
        
        status = get_delivery_status(db, load_b.id, "company-a")
        assert status is None  # Should not find it


class TestErrorHandling:
    """Test proper error handling without information leakage"""
    
    def test_errors_do_not_expose_stack_traces(
        self,
        client: TestClient,
        company_a_token
    ):
        """
        Test that errors don't expose internal stack traces or details.
        
        Security Issue #14: Error context leakage
        """
        # Try to get non-existent load
        response = client.get(
            "/api/loads/invalid-load-id",
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        assert response.status_code == 404
        error = response.json()
        
        # Error should not contain stack traces
        assert "Traceback" not in str(error)
        assert "File" not in str(error)
        assert "line" not in str(error).lower()
        
        # Error should be user-friendly
        assert len(error["detail"]) < 200  # Short message
    
    def test_database_errors_dont_expose_internals(
        self,
        client: TestClient,
        company_a_token
    ):
        """Test that database errors don't expose SQL or internal details."""
        # Try to create load with invalid data (trigger DB error)
        response = client.post(
            "/api/loads/",
            json={
                "pickupLocation": "A",
                "deliveryLocation": "B",
                # Missing required fields or causing DB constraint violation
            },
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        
        # Should fail gracefully
        assert response.status_code in [400, 500]
        error = response.json()
        
        # Should not expose SQL or database internals
        assert "SQL" not in str(error)
        assert "database" not in error.get("detail", "").lower()


@pytest.mark.integration
class TestEndToEndMultiTenancy:
    """End-to-end tests for multi-tenant workflows"""
    
    def test_complete_dispatch_workflow_isolated(
        self,
        client: TestClient,
        company_a_token,
        company_b_token,
        db: Session
    ):
        """
        Test that a complete dispatch workflow maintains tenant isolation.
        """
        # Company A creates a load
        create_response = client.post(
            "/api/loads/",
            json={
                "pickupLocation": "Warehouse A",
                "deliveryLocation": "Destination A",
                "rate": 1500
            },
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        assert create_response.status_code == 201
        load_a_id = create_response.json()["id"]
        
        # Company B creates a load
        create_response = client.post(
            "/api/loads/",
            json={
                "pickupLocation": "Warehouse B",
                "deliveryLocation": "Destination B",
                "rate": 2500
            },
            headers={"Authorization": f"Bearer {company_b_token}"}
        )
        assert create_response.status_code == 201
        load_b_id = create_response.json()["id"]
        
        # Company A lists loads - should only see their own
        list_response = client.get(
            "/api/loads/",
            headers={"Authorization": f"Bearer {company_a_token}"}
        )
        assert list_response.status_code == 200
        loads = list_response.json()["items"]
        load_ids = [l["id"] for l in loads]
        
        assert load_a_id in load_ids
        assert load_b_id not in load_ids
        
        # Company B lists loads - should only see their own
        list_response = client.get(
            "/api/loads/",
            headers={"Authorization": f"Bearer {company_b_token}"}
        )
        assert list_response.status_code == 200
        loads = list_response.json()["items"]
        load_ids = [l["id"] for l in loads]
        
        assert load_b_id in load_ids
        assert load_a_id not in load_ids


# Run with: pytest tests/test_dispatch_multi_tenant.py -v

