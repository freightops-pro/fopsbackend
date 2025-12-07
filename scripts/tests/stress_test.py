"""
Backend Stress Test Suite using Locust
Run with: locust -f stress_test.py --host=http://127.0.0.1:8000

For headless mode with automatic scaling:
locust -f stress_test.py --host=http://127.0.0.1:8000 --headless -u 1000 -r 50 --run-time 5m
"""

import json
import random
import string
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner
import time


def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


class FreightOpsUser(HttpUser):
    """Simulates a typical FreightOps user interacting with the API."""

    wait_time = between(0.1, 0.5)  # Very aggressive timing for stress test

    def on_start(self):
        """Called when a simulated user starts."""
        self.token = None
        self.company_id = None
        # Try to login (will fail without valid creds, but tests the endpoint)
        self.login()

    def login(self):
        """Attempt to login and get auth token."""
        try:
            response = self.client.post(
                "/api/auth/login",
                json={
                    "email": f"stresstest_{random_string(5)}@test.com",
                    "password": "StressTest123!"
                },
                catch_response=True
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.company_id = data.get("company_id")
                response.success()
            else:
                # Expected to fail with invalid creds, mark as success for stress test
                response.success()
        except Exception as e:
            pass

    @property
    def auth_headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    # ============== Health Check Endpoints ==============
    @task(10)
    def health_check(self):
        """Hit the main health endpoint - high frequency."""
        self.client.get("/health")

    @task(10)
    def api_health_check(self):
        """Hit the API health endpoint."""
        self.client.get("/api/healthz")

    @task(5)
    def root_endpoint(self):
        """Hit the root endpoint."""
        self.client.get("/")

    # ============== Tenant Features ==============
    @task(8)
    def get_tenant_features(self):
        """Get tenant features - common API call."""
        self.client.get("/api/tenant/features", headers=self.auth_headers)

    # ============== Dispatch Endpoints ==============
    @task(5)
    def list_loads(self):
        """List dispatch loads."""
        self.client.get("/api/dispatch/loads", headers=self.auth_headers)

    @task(3)
    def list_loads_with_filters(self):
        """List loads with various filters."""
        params = {
            "status": random.choice(["pending", "in_transit", "delivered", "cancelled"]),
            "limit": random.choice([10, 25, 50, 100]),
            "offset": random.randint(0, 100)
        }
        self.client.get("/api/dispatch/loads", params=params, headers=self.auth_headers)

    # ============== Driver Endpoints ==============
    @task(4)
    def list_drivers(self):
        """List drivers."""
        self.client.get("/api/drivers", headers=self.auth_headers)

    @task(2)
    def get_driver_compliance(self):
        """Get driver compliance info."""
        self.client.get("/api/drivers/compliance", headers=self.auth_headers)

    # ============== Fleet Endpoints ==============
    @task(4)
    def list_fleet(self):
        """List fleet equipment."""
        self.client.get("/api/fleet", headers=self.auth_headers)

    @task(2)
    def list_equipment(self):
        """List equipment."""
        self.client.get("/api/fleet/equipment", headers=self.auth_headers)

    # ============== Dashboard Endpoints ==============
    @task(6)
    def dashboard_metrics(self):
        """Get dashboard metrics - heavy endpoint."""
        self.client.get("/api/dashboard/metrics", headers=self.auth_headers)

    @task(3)
    def dashboard_stats(self):
        """Get dashboard stats."""
        self.client.get("/api/dashboard/stats", headers=self.auth_headers)

    # ============== Accounting Endpoints ==============
    @task(3)
    def list_invoices(self):
        """List invoices."""
        self.client.get("/api/accounting/invoices", headers=self.auth_headers)

    @task(2)
    def get_ar_summary(self):
        """Get AR summary."""
        self.client.get("/api/accounting/ar/summary", headers=self.auth_headers)

    # ============== Fuel & IFTA Endpoints ==============
    @task(2)
    def list_fuel_transactions(self):
        """List fuel transactions."""
        self.client.get("/api/fuel/transactions", headers=self.auth_headers)

    @task(1)
    def get_ifta_report(self):
        """Get IFTA report - compute heavy."""
        self.client.get("/api/fuel/ifta/report", headers=self.auth_headers)

    # ============== Ports Endpoints ==============
    @task(2)
    def list_ports(self):
        """List ports."""
        self.client.get("/api/ports", headers=self.auth_headers)

    # ============== Usage Ledger Endpoints ==============
    @task(2)
    def list_usage_entries(self):
        """List usage ledger entries."""
        self.client.get("/api/usage-ledger/entries", headers=self.auth_headers)

    # ============== Reporting Endpoints ==============
    @task(2)
    def get_reports(self):
        """Get reports list."""
        self.client.get("/api/reporting", headers=self.auth_headers)

    # ============== Heavy Operations (Lower Frequency) ==============
    @task(1)
    def create_load_attempt(self):
        """Attempt to create a load - write operation."""
        load_data = {
            "reference_number": f"STRESS-{random_string(8)}",
            "origin": "Los Angeles, CA",
            "destination": "New York, NY",
            "pickup_date": "2024-12-01",
            "delivery_date": "2024-12-05",
            "rate": random.uniform(1000, 5000),
            "weight": random.randint(10000, 45000),
            "commodity": "General Freight"
        }
        self.client.post(
            "/api/dispatch/loads",
            json=load_data,
            headers=self.auth_headers,
            catch_response=True
        )

    @task(1)
    def automation_status(self):
        """Check automation status."""
        self.client.get("/api/automation/status", headers=self.auth_headers)


class AggressiveUser(HttpUser):
    """Very aggressive user for maximum stress."""

    wait_time = between(0.01, 0.1)  # Almost no wait

    @task(20)
    def rapid_health(self):
        """Rapid fire health checks."""
        self.client.get("/health")

    @task(15)
    def rapid_api_health(self):
        """Rapid fire API health checks."""
        self.client.get("/api/healthz")

    @task(10)
    def rapid_tenant_features(self):
        """Rapid fire tenant features."""
        self.client.get("/api/tenant/features")

    @task(10)
    def rapid_loads(self):
        """Rapid fire loads listing."""
        self.client.get("/api/dispatch/loads")

    @task(5)
    def rapid_dashboard(self):
        """Rapid fire dashboard - heavy endpoint."""
        self.client.get("/api/dashboard/metrics")


class DatabaseHeavyUser(HttpUser):
    """User focused on database-heavy operations."""

    wait_time = between(0.1, 0.3)

    @task(5)
    def query_loads_pagination(self):
        """Query loads with pagination - stresses DB."""
        for page in range(5):
            self.client.get(f"/api/dispatch/loads?offset={page*50}&limit=50")

    @task(3)
    def query_drivers_filter(self):
        """Query drivers with filters."""
        self.client.get("/api/drivers?status=active&limit=100")

    @task(3)
    def query_equipment_filter(self):
        """Query equipment with filters."""
        self.client.get("/api/fleet/equipment?status=available")

    @task(2)
    def complex_report_query(self):
        """Complex reporting query - very heavy."""
        self.client.get("/api/reporting/summary?period=30d")

    @task(2)
    def accounting_heavy(self):
        """Heavy accounting queries."""
        self.client.get("/api/accounting/ar/aging")


# Statistics tracking
request_stats = {
    "total_requests": 0,
    "failures": 0,
    "avg_response_time": 0,
    "max_response_time": 0,
}

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Track request statistics."""
    request_stats["total_requests"] += 1
    if exception:
        request_stats["failures"] += 1
    if response_time > request_stats["max_response_time"]:
        request_stats["max_response_time"] = response_time


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print final statistics."""
    print("\n" + "="*60)
    print("STRESS TEST COMPLETE")
    print("="*60)
    print(f"Total Requests: {request_stats['total_requests']}")
    print(f"Failures: {request_stats['failures']}")
    print(f"Max Response Time: {request_stats['max_response_time']:.2f}ms")
    print("="*60 + "\n")


if __name__ == "__main__":
    import os
    print("""
╔══════════════════════════════════════════════════════════════╗
║           FreightOps Backend Stress Test Suite               ║
╠══════════════════════════════════════════════════════════════╣
║  Run with:                                                   ║
║    locust -f stress_test.py --host=http://127.0.0.1:8000    ║
║                                                              ║
║  For headless mode (auto-scaling until crash):              ║
║    locust -f stress_test.py --host=http://127.0.0.1:8000 \  ║
║          --headless -u 1000 -r 50 --run-time 5m             ║
║                                                              ║
║  Web UI available at: http://localhost:8089                  ║
╚══════════════════════════════════════════════════════════════╝
    """)
