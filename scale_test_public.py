"""
FreightOps Scale Test - Public Endpoints Only
Tests the system capacity using only public endpoints (health, docs)
to measure true system limits without authentication interference.

Run: python scale_test_public.py
"""

import asyncio
import aiohttp
import time
import random
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional
import psutil

# Configuration
BASE_URL = "http://127.0.0.1:8000"
API_URL = f"{BASE_URL}/api"

# Scale parameters - aggressive testing
INITIAL_CONCURRENT_USERS = 50
MAX_CONCURRENT_USERS = 5000
USER_SCALE_FACTOR = 2

REQUEST_TIMEOUT = 30
ROUND_DURATION = 30  # seconds per round


@dataclass
class ScaleMetrics:
    round_number: int = 0
    concurrent_users: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0
    max_response_time_ms: float = 0
    min_response_time_ms: float = float('inf')
    errors: List[str] = field(default_factory=list)
    system_cpu_percent: float = 0
    system_memory_percent: float = 0
    requests_per_second: float = 0

    def to_dict(self) -> dict:
        return {
            "round": self.round_number,
            "concurrent_users": self.concurrent_users,
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


class PublicScaleTester:
    """Scale tester focused on public endpoints only."""

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
    ) -> tuple[bool, float, str]:
        """Make a single HTTP request."""
        start = time.perf_counter()
        try:
            async with session.request(
                method,
                url,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                elapsed = (time.perf_counter() - start) * 1000
                await response.read()

                async with self.lock:
                    self.response_times.append(elapsed)
                    self.current_metrics.total_requests += 1

                    if response.status == 200:
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

    async def simulate_user(self, session: aiohttp.ClientSession, duration: float):
        """Simulate user making requests to public endpoints."""
        end_time = time.time() + duration

        # Public endpoints only
        endpoints = [
            f"{BASE_URL}/health",  # Main health
            f"{BASE_URL}/",  # Root
            f"{API_URL}/healthz",  # API health
        ]

        while time.time() < end_time and not self.crashed:
            try:
                url = random.choice(endpoints)
                result = await self.make_request(session, "GET", url)

                if not result[0] and "Cannot connect" in result[2]:
                    self.crashed = True
                    self.crash_reason = f"Server unreachable: {result[2]}"
                    break

                # Very small delay - stress test
                await asyncio.sleep(random.uniform(0.001, 0.01))

            except Exception as e:
                if "Cannot connect" in str(e) or "Connection refused" in str(e):
                    self.crashed = True
                    self.crash_reason = f"Server unreachable: {e}"
                    break

    async def run_scale_round(self, round_num: int, num_users: int) -> ScaleMetrics:
        """Run a single round of scale testing."""
        self.current_metrics = ScaleMetrics(
            round_number=round_num,
            concurrent_users=num_users,
        )
        self.response_times = []

        print(f"\n{'='*70}")
        print(f"ROUND {round_num}: {num_users} concurrent users (public endpoints)")
        print(f"{'='*70}")

        connector = aiohttp.TCPConnector(
            limit=min(num_users * 3, 2000),
            limit_per_host=min(num_users * 2, 1000),
            ttl_dns_cache=300,
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            # Verify server
            try:
                async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        print(f"[FAIL] Server health check failed: HTTP {resp.status}")
                        self.crashed = True
                        self.crash_reason = f"Health check failed: HTTP {resp.status}"
                        return self.current_metrics
            except Exception as e:
                print(f"[FAIL] Server unreachable: {e}")
                self.crashed = True
                self.crash_reason = str(e)
                return self.current_metrics

            # Launch users
            tasks = [self.simulate_user(session, ROUND_DURATION) for _ in range(num_users)]

            start = time.time()
            done_event = asyncio.Event()

            async def progress_tracker():
                while not done_event.is_set():
                    elapsed = time.time() - start
                    rps = self.current_metrics.total_requests / max(elapsed, 0.1)
                    success_rate = (self.current_metrics.successful_requests /
                                  max(self.current_metrics.total_requests, 1) * 100)
                    print(
                        f"\r  [{elapsed:.0f}s] Requests: {self.current_metrics.total_requests:,} | "
                        f"RPS: {rps:.0f} | Success: {success_rate:.1f}% | "
                        f"Errors: {self.current_metrics.failed_requests:,}",
                        end="", flush=True
                    )
                    await asyncio.sleep(1)

            progress_task = asyncio.create_task(progress_tracker())
            await asyncio.gather(*tasks, return_exceptions=True)
            done_event.set()
            await progress_task

        # Calculate final metrics
        duration = time.time() - start

        if self.response_times:
            self.current_metrics.avg_response_time_ms = sum(self.response_times) / len(self.response_times)
            self.current_metrics.max_response_time_ms = max(self.response_times)
            self.current_metrics.min_response_time_ms = min(self.response_times)

        self.current_metrics.requests_per_second = self.current_metrics.total_requests / max(duration, 0.1)
        self.current_metrics.system_cpu_percent = psutil.cpu_percent()
        self.current_metrics.system_memory_percent = psutil.virtual_memory().percent

        self.metrics_history.append(self.current_metrics)

        # Print summary
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
                print(f"    - {err[:60]}")

        return self.current_metrics

    async def run_scale_test(self):
        """Run the full scale test."""
        print("""
======================================================================
   FreightOps Scale Test - PUBLIC ENDPOINTS (Health Checks)
======================================================================
  Testing system capacity with public endpoints only.
  Press Ctrl+C to stop at any time.
======================================================================
        """)

        round_num = 0
        num_users = INITIAL_CONCURRENT_USERS

        try:
            while not self.crashed and num_users <= MAX_CONCURRENT_USERS:
                round_num += 1
                metrics = await self.run_scale_round(round_num, num_users)

                # Check for system crash (>20% failure on public endpoints)
                if metrics.total_requests > 0:
                    failure_rate = metrics.failed_requests / metrics.total_requests
                    if failure_rate > 0.2:
                        print(f"\n[WARN] High failure rate detected ({failure_rate*100:.1f}%)")
                        self.crashed = True
                        self.crash_reason = f"Failure rate exceeded 20% ({failure_rate*100:.1f}%)"
                        break

                # Check response time degradation (>5 seconds average)
                if metrics.avg_response_time_ms > 5000:
                    print(f"\n[WARN] Severe response time degradation")
                    self.crashed = True
                    self.crash_reason = f"Avg response time: {metrics.avg_response_time_ms:.0f}ms"
                    break

                # Scale up
                num_users = min(int(num_users * USER_SCALE_FACTOR), MAX_CONCURRENT_USERS)
                print(f"\n  Scaling up to {num_users} users...")
                await asyncio.sleep(3)

        except KeyboardInterrupt:
            print("\n\n[WARN] Test interrupted by user")
            self.crash_reason = "User interrupt"

        except Exception as e:
            print(f"\n\n[ERROR] Unexpected error: {e}")
            self.crashed = True
            self.crash_reason = str(e)

        self.print_final_report()

    def print_final_report(self):
        """Print final report."""
        print("""
======================================================================
                     FINAL SCALE TEST REPORT
======================================================================
        """)

        if self.crashed:
            print(f"[LIMIT] SYSTEM LIMIT REACHED")
            print(f"   Reason: {self.crash_reason}")
        else:
            print("[OK] Completed all rounds successfully")

        print("\n[STATS] Performance by Scale Level:\n")
        print(f"{'Round':<6} {'Users':<10} {'RPS':<12} {'Avg(ms)':<12} {'Max(ms)':<12} {'Success':<10}")
        print("-" * 70)

        for m in self.metrics_history:
            success_rate = (m.successful_requests / max(m.total_requests, 1)) * 100
            print(
                f"{m.round_number:<6} {m.concurrent_users:<10} {m.requests_per_second:<12.1f} "
                f"{m.avg_response_time_ms:<12.1f} {m.max_response_time_ms:<12.1f} {success_rate:<10.1f}%"
            )

        # Find max stable capacity
        if self.metrics_history:
            stable_rounds = [m for m in self.metrics_history
                          if m.successful_requests / max(m.total_requests, 1) >= 0.95]
            if stable_rounds:
                last_good = stable_rounds[-1]
                print(f"\n[CAPACITY] MAXIMUM STABLE CAPACITY:")
                print(f"   - {last_good.concurrent_users} concurrent users")
                print(f"   - {last_good.requests_per_second:.1f} requests/second")
                print(f"   - {last_good.avg_response_time_ms:.1f}ms average response")
            else:
                print("\n[INFO] Finding optimal point...")
                best = max(self.metrics_history,
                          key=lambda m: m.requests_per_second if m.successful_requests/max(m.total_requests,1) > 0.8 else 0)
                print(f"\n[CAPACITY] BEST PERFORMANCE:")
                print(f"   - {best.concurrent_users} concurrent users")
                print(f"   - {best.requests_per_second:.1f} requests/second")

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"scale_test_public_{timestamp}.json"
        with open(results_file, "w") as f:
            json.dump({
                "crashed": self.crashed,
                "crash_reason": self.crash_reason,
                "rounds": [m.to_dict() for m in self.metrics_history]
            }, f, indent=2)
        print(f"\n[SAVED] Results saved to: {results_file}")


async def main():
    print("FreightOps Public Endpoint Scale Test")
    print("=" * 50)

    # Quick connectivity test
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    print(f"[OK] Server is responding at {BASE_URL}")
                else:
                    print(f"[FAIL] Server returned HTTP {resp.status}")
                    return
        except Exception as e:
            print(f"[FAIL] Cannot connect to server: {e}")
            return

    print("\nStarting scale test in 3 seconds...")
    await asyncio.sleep(3)

    tester = PublicScaleTester()
    await tester.run_scale_test()


if __name__ == "__main__":
    asyncio.run(main())
