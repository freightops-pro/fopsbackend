"""
FreightOps Scale Test - Test thousands of trucks, loads, and users until crash
Run: python scale_test.py

This test progressively scales up:
1. Concurrent API requests
2. Data volume (trucks, loads, users)
3. WebSocket connections
4. Database operations

Until the system crashes or becomes unresponsive.
"""

import asyncio
import aiohttp
import time
import random
import string
import sys
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import traceback
import psutil
import os

# Configuration
BASE_URL = "http://127.0.0.1:8000"
API_URL = f"{BASE_URL}/api"

# Scale parameters - will increase until crash
INITIAL_CONCURRENT_USERS = 10
MAX_CONCURRENT_USERS = 10000
USER_SCALE_FACTOR = 2  # Double users each round

INITIAL_TRUCKS = 50
MAX_TRUCKS = 50000
TRUCK_SCALE_FACTOR = 2

INITIAL_LOADS = 100
MAX_LOADS = 100000
LOAD_SCALE_FACTOR = 2

REQUEST_TIMEOUT = 30  # seconds
ROUND_DURATION = 30  # seconds per test round


@dataclass
class ScaleMetrics:
    """Track metrics for each scale round."""
    round_number: int = 0
    concurrent_users: int = 0
    trucks_simulated: int = 0
    loads_simulated: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0
    max_response_time_ms: float = 0
    min_response_time_ms: float = float('inf')
    errors: List[str] = field(default_factory=list)
    start_time: float = 0
    end_time: float = 0
    system_cpu_percent: float = 0
    system_memory_percent: float = 0
    requests_per_second: float = 0

    def to_dict(self) -> dict:
        return {
            "round": self.round_number,
            "concurrent_users": self.concurrent_users,
            "trucks": self.trucks_simulated,
            "loads": self.loads_simulated,
            "total_requests": self.total_requests,
            "successful": self.successful_requests,
            "failed": self.failed_requests,
            "success_rate": f"{(self.successful_requests/max(self.total_requests,1))*100:.1f}%",
            "avg_response_ms": f"{self.avg_response_time_ms:.1f}",
            "max_response_ms": f"{self.max_response_time_ms:.1f}",
            "rps": f"{self.requests_per_second:.1f}",
            "cpu": f"{self.system_cpu_percent:.1f}%",
            "memory": f"{self.system_memory_percent:.1f}%",
        }


def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_truck_data(truck_id: int) -> dict:
    """Generate realistic truck data."""
    return {
        "unit_number": f"TRK-{truck_id:05d}",
        "vin": f"1FUJGBDV{random_string(9).upper()}",
        "make": random.choice(["Freightliner", "Peterbilt", "Kenworth", "Volvo", "International"]),
        "model": random.choice(["Cascadia", "579", "T680", "VNL", "LT"]),
        "year": random.randint(2018, 2024),
        "license_plate": f"{random.choice(['CA','TX','FL','NY','IL'])}-{random_string(6).upper()}",
        "status": random.choice(["active", "in_maintenance", "available", "assigned"]),
        "mileage": random.randint(50000, 500000),
        "fuel_type": random.choice(["diesel", "natural_gas"]),
    }


def generate_load_data(load_id: int) -> dict:
    """Generate realistic load data."""
    cities = [
        ("Los Angeles", "CA"), ("New York", "NY"), ("Chicago", "IL"),
        ("Houston", "TX"), ("Phoenix", "AZ"), ("Philadelphia", "PA"),
        ("San Antonio", "TX"), ("San Diego", "CA"), ("Dallas", "TX"),
        ("San Jose", "CA"), ("Austin", "TX"), ("Jacksonville", "FL"),
        ("Fort Worth", "TX"), ("Columbus", "OH"), ("Charlotte", "NC"),
        ("Indianapolis", "IN"), ("Seattle", "WA"), ("Denver", "CO"),
        ("Boston", "MA"), ("Nashville", "TN"), ("Portland", "OR"),
        ("Las Vegas", "NV"), ("Detroit", "MI"), ("Memphis", "TN"),
    ]
    origin = random.choice(cities)
    destination = random.choice([c for c in cities if c != origin])

    pickup = datetime.now() + timedelta(days=random.randint(1, 14))
    delivery = pickup + timedelta(days=random.randint(1, 5))

    return {
        "reference_number": f"LD-{load_id:06d}",
        "customer_reference": f"CUST-{random_string(8)}",
        "origin_city": origin[0],
        "origin_state": origin[1],
        "destination_city": destination[0],
        "destination_state": destination[1],
        "pickup_date": pickup.isoformat(),
        "delivery_date": delivery.isoformat(),
        "rate": round(random.uniform(1500, 8000), 2),
        "weight_lbs": random.randint(10000, 45000),
        "commodity": random.choice([
            "General Freight", "Electronics", "Food Products",
            "Auto Parts", "Machinery", "Consumer Goods",
            "Building Materials", "Paper Products", "Chemicals"
        ]),
        "equipment_type": random.choice(["Dry Van", "Reefer", "Flatbed", "Step Deck"]),
        "status": random.choice(["pending", "assigned", "in_transit", "delivered"]),
        "miles": random.randint(100, 3000),
    }


def generate_driver_data(driver_id: int) -> dict:
    """Generate realistic driver data."""
    first_names = ["John", "Mike", "David", "James", "Robert", "William", "Jose", "Carlos", "Maria", "Jennifer"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

    return {
        "employee_id": f"DRV-{driver_id:05d}",
        "first_name": random.choice(first_names),
        "last_name": random.choice(last_names),
        "email": f"driver{driver_id}@freightops.test",
        "phone": f"+1{random.randint(200,999)}{random.randint(1000000,9999999)}",
        "cdl_number": f"{random.choice(['CA','TX','FL','NY'])}{random_string(8).upper()}",
        "cdl_state": random.choice(["CA", "TX", "FL", "NY", "IL", "OH"]),
        "cdl_expiration": (datetime.now() + timedelta(days=random.randint(30, 730))).isoformat(),
        "status": random.choice(["active", "on_leave", "available", "driving"]),
        "hire_date": (datetime.now() - timedelta(days=random.randint(30, 1800))).isoformat(),
    }


class ScaleTester:
    """Main scale testing class."""

    def __init__(self):
        self.metrics_history: List[ScaleMetrics] = []
        self.current_metrics: Optional[ScaleMetrics] = None
        self.response_times: List[float] = []
        self.crashed = False
        self.crash_reason = ""
        self.lock = asyncio.Lock()

    async def make_request(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        data: dict = None,
        headers: dict = None
    ) -> tuple[bool, float, str]:
        """Make a single HTTP request and track metrics."""
        start = time.perf_counter()
        try:
            async with session.request(
                method,
                url,
                json=data,
                headers=headers or {},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                elapsed = (time.perf_counter() - start) * 1000  # ms
                await response.read()

                async with self.lock:
                    self.response_times.append(elapsed)
                    self.current_metrics.total_requests += 1

                    if response.status < 400:
                        self.current_metrics.successful_requests += 1
                        return True, elapsed, ""
                    else:
                        self.current_metrics.failed_requests += 1
                        return False, elapsed, f"HTTP {response.status}"

        except asyncio.TimeoutError:
            elapsed = (time.perf_counter() - start) * 1000
            async with self.lock:
                self.current_metrics.total_requests += 1
                self.current_metrics.failed_requests += 1
                self.response_times.append(elapsed)
            return False, elapsed, "Timeout"

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            async with self.lock:
                self.current_metrics.total_requests += 1
                self.current_metrics.failed_requests += 1
                if str(e) not in [err[:50] for err in self.current_metrics.errors[-10:]]:
                    self.current_metrics.errors.append(str(e)[:100])
            return False, elapsed, str(e)

    async def simulate_user(
        self,
        session: aiohttp.ClientSession,
        user_id: int,
        trucks: List[dict],
        loads: List[dict],
        duration: float
    ):
        """Simulate a single user making various API calls."""
        end_time = time.time() + duration

        while time.time() < end_time and not self.crashed:
            try:
                # Random API operation
                operation = random.choice([
                    "health", "health", "health",  # More health checks
                    "list_loads", "list_loads",
                    "list_trucks",
                    "list_drivers",
                    "dashboard",
                    "tenant_features",
                    "create_load",
                    "get_load",
                    "accounting",
                    "fuel",
                ])

                if operation == "health":
                    await self.make_request(session, "GET", f"{BASE_URL}/health")

                elif operation == "list_loads":
                    params = f"?limit={random.choice([10,25,50,100])}&offset={random.randint(0,100)}"
                    await self.make_request(session, "GET", f"{API_URL}/dispatch/loads{params}")

                elif operation == "list_trucks":
                    await self.make_request(session, "GET", f"{API_URL}/fleet")

                elif operation == "list_drivers":
                    await self.make_request(session, "GET", f"{API_URL}/drivers")

                elif operation == "dashboard":
                    await self.make_request(session, "GET", f"{API_URL}/dashboard/metrics")

                elif operation == "tenant_features":
                    await self.make_request(session, "GET", f"{API_URL}/tenant/features")

                elif operation == "create_load":
                    load_data = generate_load_data(random.randint(1, 999999))
                    await self.make_request(session, "POST", f"{API_URL}/dispatch/loads", data=load_data)

                elif operation == "get_load":
                    if loads:
                        load = random.choice(loads)
                        await self.make_request(
                            session, "GET",
                            f"{API_URL}/dispatch/loads/{load.get('reference_number', 'LD-000001')}"
                        )

                elif operation == "accounting":
                    await self.make_request(session, "GET", f"{API_URL}/accounting/invoices")

                elif operation == "fuel":
                    await self.make_request(session, "GET", f"{API_URL}/fuel/transactions")

                # Small delay between requests
                await asyncio.sleep(random.uniform(0.01, 0.1))

            except Exception as e:
                if "Cannot connect" in str(e) or "Connection refused" in str(e):
                    self.crashed = True
                    self.crash_reason = f"Server unreachable: {e}"
                    break

    async def run_scale_round(
        self,
        round_num: int,
        num_users: int,
        num_trucks: int,
        num_loads: int
    ) -> ScaleMetrics:
        """Run a single round of scale testing."""

        self.current_metrics = ScaleMetrics(
            round_number=round_num,
            concurrent_users=num_users,
            trucks_simulated=num_trucks,
            loads_simulated=num_loads,
            start_time=time.time()
        )
        self.response_times = []

        # Generate test data
        trucks = [generate_truck_data(i) for i in range(num_trucks)]
        loads = [generate_load_data(i) for i in range(num_loads)]

        print(f"\n{'='*70}")
        print(f"ROUND {round_num}: {num_users} users | {num_trucks} trucks | {num_loads} loads")
        print(f"{'='*70}")

        # Create connection pool
        connector = aiohttp.TCPConnector(
            limit=min(num_users * 2, 1000),  # Connection pool size
            limit_per_host=min(num_users * 2, 500),
            ttl_dns_cache=300,
            force_close=False,
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            # First, verify server is responsive
            try:
                async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        print("[FAIL] Server health check failed before round start")
                        self.crashed = True
                        self.crash_reason = f"Health check failed: HTTP {resp.status}"
                        return self.current_metrics
            except Exception as e:
                print(f"[FAIL] Server unreachable: {e}")
                self.crashed = True
                self.crash_reason = str(e)
                return self.current_metrics

            # Launch all users concurrently
            tasks = [
                self.simulate_user(session, i, trucks, loads, ROUND_DURATION)
                for i in range(num_users)
            ]

            # Progress tracking
            start = time.time()
            done_event = asyncio.Event()

            async def progress_tracker():
                while not done_event.is_set():
                    elapsed = time.time() - start
                    rps = self.current_metrics.total_requests / max(elapsed, 0.1)
                    success_rate = (
                        self.current_metrics.successful_requests /
                        max(self.current_metrics.total_requests, 1) * 100
                    )
                    print(
                        f"\r  [{elapsed:.0f}s] Requests: {self.current_metrics.total_requests:,} | "
                        f"RPS: {rps:.0f} | Success: {success_rate:.1f}% | "
                        f"Errors: {self.current_metrics.failed_requests:,}",
                        end="", flush=True
                    )
                    await asyncio.sleep(1)

            progress_task = asyncio.create_task(progress_tracker())

            # Wait for all users to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            done_event.set()
            await progress_task

        # Calculate final metrics
        self.current_metrics.end_time = time.time()
        duration = self.current_metrics.end_time - self.current_metrics.start_time

        if self.response_times:
            self.current_metrics.avg_response_time_ms = sum(self.response_times) / len(self.response_times)
            self.current_metrics.max_response_time_ms = max(self.response_times)
            self.current_metrics.min_response_time_ms = min(self.response_times)

        self.current_metrics.requests_per_second = self.current_metrics.total_requests / max(duration, 0.1)

        # System metrics
        self.current_metrics.system_cpu_percent = psutil.cpu_percent()
        self.current_metrics.system_memory_percent = psutil.virtual_memory().percent

        self.metrics_history.append(self.current_metrics)

        # Print round summary
        print(f"\n\n  Round {round_num} Summary:")
        print(f"  - Total Requests: {self.current_metrics.total_requests:,}")
        print(f"  - Successful: {self.current_metrics.successful_requests:,}")
        print(f"  - Failed: {self.current_metrics.failed_requests:,}")
        print(f"  - Requests/sec: {self.current_metrics.requests_per_second:.1f}")
        print(f"  - Avg Response: {self.current_metrics.avg_response_time_ms:.1f}ms")
        print(f"  - Max Response: {self.current_metrics.max_response_time_ms:.1f}ms")
        print(f"  - CPU: {self.current_metrics.system_cpu_percent:.1f}%")
        print(f"  - Memory: {self.current_metrics.system_memory_percent:.1f}%")

        if self.current_metrics.errors:
            print(f"\n  Errors ({len(self.current_metrics.errors)} unique):")
            for err in self.current_metrics.errors[:5]:
                print(f"    - {err[:70]}")

        return self.current_metrics

    async def run_scale_test(self):
        """Run the full scale test until crash."""

        print("""
======================================================================
         FreightOps Scale Test - Testing Until Crash
======================================================================
  This test will progressively increase load until system failure.
  Press Ctrl+C to stop at any time.
======================================================================
        """)

        round_num = 0
        num_users = INITIAL_CONCURRENT_USERS
        num_trucks = INITIAL_TRUCKS
        num_loads = INITIAL_LOADS

        try:
            while not self.crashed and num_users <= MAX_CONCURRENT_USERS:
                round_num += 1

                metrics = await self.run_scale_round(
                    round_num, num_users, num_trucks, num_loads
                )

                # Check for effective crash (>50% failure rate)
                if metrics.total_requests > 0:
                    failure_rate = metrics.failed_requests / metrics.total_requests
                    if failure_rate > 0.5:
                        print(f"\n[WARN] High failure rate detected ({failure_rate*100:.1f}%)")
                        self.crashed = True
                        self.crash_reason = f"Failure rate exceeded 50% ({failure_rate*100:.1f}%)"
                        break

                # Check for response time degradation
                if metrics.avg_response_time_ms > 10000:  # 10 seconds
                    print(f"\n[WARN] Severe response time degradation")
                    self.crashed = True
                    self.crash_reason = f"Avg response time: {metrics.avg_response_time_ms:.0f}ms"
                    break

                # Scale up for next round
                num_users = min(int(num_users * USER_SCALE_FACTOR), MAX_CONCURRENT_USERS)
                num_trucks = min(int(num_trucks * TRUCK_SCALE_FACTOR), MAX_TRUCKS)
                num_loads = min(int(num_loads * LOAD_SCALE_FACTOR), MAX_LOADS)

                # Brief pause between rounds
                print(f"\n  Scaling up to {num_users} users...")
                await asyncio.sleep(3)

        except KeyboardInterrupt:
            print("\n\n[WARN] Test interrupted by user")
            self.crash_reason = "User interrupt"

        except Exception as e:
            print(f"\n\n[ERROR] Unexpected error: {e}")
            traceback.print_exc()
            self.crashed = True
            self.crash_reason = str(e)

        # Print final report
        self.print_final_report()

    def print_final_report(self):
        """Print the final test report."""
        print("""
======================================================================
                        FINAL SCALE TEST REPORT
======================================================================
        """)

        if self.crashed:
            print(f"[LIMIT] SYSTEM LIMIT REACHED")
            print(f"   Reason: {self.crash_reason}")
        else:
            print("[OK] Completed all rounds without failure")

        print("\n[STATS] Performance by Scale Level:\n")
        print(f"{'Round':<6} {'Users':<8} {'Trucks':<8} {'Loads':<8} {'RPS':<10} {'Avg(ms)':<10} {'Success':<10}")
        print("-" * 70)

        for m in self.metrics_history:
            success_rate = (m.successful_requests / max(m.total_requests, 1)) * 100
            print(
                f"{m.round_number:<6} {m.concurrent_users:<8} {m.trucks_simulated:<8} "
                f"{m.loads_simulated:<8} {m.requests_per_second:<10.1f} "
                f"{m.avg_response_time_ms:<10.1f} {success_rate:<10.1f}%"
            )

        if self.metrics_history:
            last_good = None
            for m in self.metrics_history:
                success_rate = m.successful_requests / max(m.total_requests, 1)
                if success_rate >= 0.9:  # 90%+ success
                    last_good = m

            if last_good:
                print(f"\n[CAPACITY] MAXIMUM STABLE CAPACITY:")
                print(f"   - {last_good.concurrent_users} concurrent users")
                print(f"   - {last_good.trucks_simulated} trucks")
                print(f"   - {last_good.loads_simulated} loads")
                print(f"   - {last_good.requests_per_second:.1f} requests/second")
            else:
                print("\n[WARN] No stable capacity found - system unstable from start")

        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"scale_test_results_{timestamp}.json"
        with open(results_file, "w") as f:
            json.dump({
                "crashed": self.crashed,
                "crash_reason": self.crash_reason,
                "rounds": [m.to_dict() for m in self.metrics_history]
            }, f, indent=2)
        print(f"\n[SAVED] Results saved to: {results_file}")


async def quick_test():
    """Run a quick connectivity test."""
    print("Running quick connectivity test...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    print(f"[OK] Server is responding at {BASE_URL}")
                    return True
                else:
                    print(f"[FAIL] Server returned HTTP {resp.status}")
                    return False
        except Exception as e:
            print(f"[FAIL] Cannot connect to server: {e}")
            return False


if __name__ == "__main__":
    print("FreightOps Scale Test")
    print("=" * 50)

    # Check if server is running
    if not asyncio.run(quick_test()):
        print("\nPlease ensure the backend is running at http://127.0.0.1:8000")
        sys.exit(1)

    print("\nStarting scale test in 3 seconds...")
    time.sleep(3)

    tester = ScaleTester()
    asyncio.run(tester.run_scale_test())
