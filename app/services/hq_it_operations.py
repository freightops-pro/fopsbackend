"""HQ IT Operations service layer."""

from __future__ import annotations

import asyncio
import httpx
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hq_it_operations import HQFeatureFlag, HQServiceHealth, HQDeployment
from app.schemas.hq_it_operations import (
    FeatureFlagCreate,
    FeatureFlagUpdate,
    FeatureFlagResponse,
    ServiceHealthCreate,
    ServiceHealthUpdate,
    ServiceHealthResponse,
    ServiceHealthCheckResult,
    DeploymentCreate,
    DeploymentResponse,
    BackgroundJobResponse,
    ITOperationsDashboard,
)

logger = logging.getLogger(__name__)


class HQFeatureFlagService:
    """Service for managing feature flags."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_flags(self) -> List[HQFeatureFlag]:
        """List all feature flags."""
        result = await self.db.execute(
            select(HQFeatureFlag).order_by(HQFeatureFlag.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_flag(self, flag_id: str) -> Optional[HQFeatureFlag]:
        """Get a feature flag by ID."""
        result = await self.db.execute(
            select(HQFeatureFlag).where(HQFeatureFlag.id == flag_id)
        )
        return result.scalar_one_or_none()

    async def get_flag_by_key(self, key: str) -> Optional[HQFeatureFlag]:
        """Get a feature flag by key."""
        result = await self.db.execute(
            select(HQFeatureFlag).where(HQFeatureFlag.key == key)
        )
        return result.scalar_one_or_none()

    async def create_flag(
        self, data: FeatureFlagCreate, created_by_id: str, created_by_name: str
    ) -> HQFeatureFlag:
        """Create a new feature flag."""
        flag = HQFeatureFlag(
            key=data.key,
            name=data.name,
            description=data.description,
            enabled=False,
            environment=data.environment,
            rollout_percentage=data.rollout_percentage,
            target_tenants=data.target_tenants,
            created_by_id=created_by_id,
            created_by_name=created_by_name,
        )
        self.db.add(flag)
        await self.db.commit()
        await self.db.refresh(flag)
        return flag

    async def update_flag(self, flag_id: str, data: FeatureFlagUpdate) -> Optional[HQFeatureFlag]:
        """Update a feature flag."""
        flag = await self.get_flag(flag_id)
        if not flag:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(flag, key, value)

        await self.db.commit()
        await self.db.refresh(flag)
        return flag

    async def toggle_flag(self, flag_id: str) -> Optional[HQFeatureFlag]:
        """Toggle a feature flag on/off."""
        flag = await self.get_flag(flag_id)
        if not flag:
            return None

        flag.enabled = not flag.enabled
        await self.db.commit()
        await self.db.refresh(flag)
        return flag

    async def delete_flag(self, flag_id: str) -> bool:
        """Delete a feature flag."""
        flag = await self.get_flag(flag_id)
        if not flag:
            return False

        await self.db.delete(flag)
        await self.db.commit()
        return True

    async def is_enabled(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Check if a feature flag is enabled for a tenant."""
        flag = await self.get_flag_by_key(key)
        if not flag or not flag.enabled:
            return False

        # Check target tenants
        if flag.target_tenants and tenant_id:
            if tenant_id in flag.target_tenants:
                return True
            # If targeting specific tenants, others get rollout percentage
            if flag.rollout_percentage < 100:
                # Simple hash-based rollout
                hash_val = hash(f"{key}:{tenant_id}") % 100
                return hash_val < flag.rollout_percentage
            return False

        # General rollout percentage
        if flag.rollout_percentage >= 100:
            return True
        if tenant_id:
            hash_val = hash(f"{key}:{tenant_id}") % 100
            return hash_val < flag.rollout_percentage

        return flag.rollout_percentage >= 100


class HQServiceHealthService:
    """Service for monitoring service health."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_services(self, include_inactive: bool = False) -> List[HQServiceHealth]:
        """List all monitored services."""
        query = select(HQServiceHealth).order_by(HQServiceHealth.name)
        if not include_inactive:
            query = query.where(HQServiceHealth.is_active == True)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_service(self, service_id: str) -> Optional[HQServiceHealth]:
        """Get a service by ID."""
        result = await self.db.execute(
            select(HQServiceHealth).where(HQServiceHealth.id == service_id)
        )
        return result.scalar_one_or_none()

    async def create_service(self, data: ServiceHealthCreate) -> HQServiceHealth:
        """Add a new service to monitor."""
        service = HQServiceHealth(
            name=data.name,
            service_type=data.service_type,
            endpoint=data.endpoint,
            health_check_url=data.health_check_url,
            region=data.region,
        )
        self.db.add(service)
        await self.db.commit()
        await self.db.refresh(service)
        return service

    async def update_service(self, service_id: str, data: ServiceHealthUpdate) -> Optional[HQServiceHealth]:
        """Update a service configuration."""
        service = await self.get_service(service_id)
        if not service:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(service, key, value)

        await self.db.commit()
        await self.db.refresh(service)
        return service

    async def check_service_health(self, service: HQServiceHealth) -> ServiceHealthCheckResult:
        """Perform a health check on a service."""
        check_url = service.health_check_url or f"https://{service.endpoint}/health"
        status = "operational"
        latency_ms = 0
        error = None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                start = datetime.utcnow()
                response = await client.get(check_url)
                latency_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

                if response.status_code >= 500:
                    status = "outage"
                    error = f"HTTP {response.status_code}"
                elif response.status_code >= 400 or latency_ms > 1000:
                    status = "degraded"
                    if latency_ms > 1000:
                        error = f"High latency: {latency_ms}ms"

        except httpx.TimeoutException:
            status = "outage"
            error = "Connection timeout"
            latency_ms = 10000
        except Exception as e:
            status = "degraded"
            error = str(e)
            latency_ms = 0

        # Update service record
        service.current_status = status
        service.current_latency_ms = latency_ms
        service.last_checked_at = datetime.utcnow()
        service.last_error = error
        await self.db.commit()

        return ServiceHealthCheckResult(
            service_id=service.id,
            status=status,
            latency_ms=latency_ms,
            error=error,
            checked_at=datetime.utcnow(),
        )

    async def check_all_services(self) -> List[ServiceHealthCheckResult]:
        """Check health of all active services."""
        services = await self.list_services()
        results = []
        for service in services:
            try:
                result = await self.check_service_health(service)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to check service {service.name}: {e}")
        return results

    async def seed_default_services(self) -> None:
        """Seed default services if none exist."""
        existing = await self.list_services(include_inactive=True)
        if existing:
            return

        default_services = [
            ServiceHealthCreate(name="Core API", service_type="internal", endpoint="api.freightopspro.com", health_check_url="https://api.freightopspro.com/health", region="US-East"),
            ServiceHealthCreate(name="Authentication Service", service_type="internal", endpoint="auth.freightopspro.com", region="US-East"),
            ServiceHealthCreate(name="PostgreSQL Primary", service_type="database", endpoint="db-primary.freightopspro.com", region="US-East"),
            ServiceHealthCreate(name="Redis Cache", service_type="cache", endpoint="redis.freightopspro.com", region="US-East"),
            ServiceHealthCreate(name="Stripe API", service_type="external", endpoint="api.stripe.com", health_check_url="https://status.stripe.com/api/v2/status.json", region="Global"),
            ServiceHealthCreate(name="Samsara ELD", service_type="external", endpoint="api.samsara.com", region="US-West"),
            ServiceHealthCreate(name="Motive ELD", service_type="external", endpoint="api.gomotive.com", region="US-East"),
        ]

        for data in default_services:
            await self.create_service(data)


class HQDeploymentService:
    """Service for tracking deployments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_deployments(
        self,
        environment: Optional[str] = None,
        limit: int = 50
    ) -> List[HQDeployment]:
        """List deployments."""
        query = select(HQDeployment).order_by(HQDeployment.started_at.desc()).limit(limit)
        if environment:
            query = query.where(HQDeployment.environment == environment)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_deployment(self, deployment_id: str) -> Optional[HQDeployment]:
        """Get a deployment by ID."""
        result = await self.db.execute(
            select(HQDeployment).where(HQDeployment.id == deployment_id)
        )
        return result.scalar_one_or_none()

    async def create_deployment(
        self,
        data: DeploymentCreate,
        deployed_by_id: str,
        deployed_by_name: str
    ) -> HQDeployment:
        """Record a new deployment."""
        deployment = HQDeployment(
            version=data.version,
            environment=data.environment,
            status="in_progress",
            commit_hash=data.commit_hash,
            changes_count=data.changes_count,
            deployed_by_id=deployed_by_id,
            deployed_by_name=deployed_by_name,
        )
        self.db.add(deployment)
        await self.db.commit()
        await self.db.refresh(deployment)
        return deployment

    async def complete_deployment(
        self,
        deployment_id: str,
        success: bool,
        error_message: Optional[str] = None
    ) -> Optional[HQDeployment]:
        """Mark a deployment as completed."""
        deployment = await self.get_deployment(deployment_id)
        if not deployment:
            return None

        deployment.status = "success" if success else "failed"
        deployment.completed_at = datetime.utcnow()
        deployment.duration_seconds = int((deployment.completed_at - deployment.started_at).total_seconds())
        deployment.error_message = error_message

        await self.db.commit()
        await self.db.refresh(deployment)
        return deployment

    async def rollback_deployment(
        self,
        deployment_id: str,
        rolled_back_by_id: str,
        rolled_back_by_name: str
    ) -> Optional[HQDeployment]:
        """Create a rollback deployment."""
        original = await self.get_deployment(deployment_id)
        if not original:
            return None

        rollback = HQDeployment(
            version=original.version,
            environment=original.environment,
            status="in_progress",
            commit_hash=original.commit_hash,
            changes_count=0,
            deployed_by_id=rolled_back_by_id,
            deployed_by_name=rolled_back_by_name,
            rollback_of_id=deployment_id,
        )
        self.db.add(rollback)

        # Mark original as rolled back
        original.status = "rolled_back"

        await self.db.commit()
        await self.db.refresh(rollback)
        return rollback

    async def get_stats(self) -> dict:
        """Get deployment statistics."""
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # Count deployments in last 30 days
        count_result = await self.db.execute(
            select(func.count(HQDeployment.id)).where(
                HQDeployment.started_at >= thirty_days_ago
            )
        )
        total = count_result.scalar() or 0

        # Count successful deployments
        success_result = await self.db.execute(
            select(func.count(HQDeployment.id)).where(
                HQDeployment.started_at >= thirty_days_ago,
                HQDeployment.status == "success"
            )
        )
        successful = success_result.scalar() or 0

        # Get current version (latest successful production deployment)
        latest_result = await self.db.execute(
            select(HQDeployment).where(
                HQDeployment.environment == "production",
                HQDeployment.status == "success"
            ).order_by(HQDeployment.completed_at.desc()).limit(1)
        )
        latest = latest_result.scalar_one_or_none()

        return {
            "total_30d": total,
            "success_rate": (successful / total * 100) if total > 0 else 100.0,
            "current_version": latest.version if latest else "v1.0.0",
        }


class HQBackgroundJobService:
    """Service for monitoring background jobs from APScheduler."""

    @staticmethod
    def get_jobs() -> List[BackgroundJobResponse]:
        """Get status of all background jobs from the scheduler."""
        from app.background.scheduler import automation_scheduler, _scheduler_lock_acquired

        jobs = []

        if not _scheduler_lock_acquired or not automation_scheduler.running:
            return jobs

        try:
            for job in automation_scheduler.get_jobs():
                job_type = "recurring"
                if "date" in str(job.trigger):
                    job_type = "scheduled"
                elif hasattr(job.trigger, "interval"):
                    job_type = "recurring"

                jobs.append(BackgroundJobResponse(
                    id=job.id,
                    name=job.name or job.id,
                    job_type=job_type,
                    status="pending",
                    next_run_time=job.next_run_time,
                    last_run_time=None,
                    last_duration_seconds=None,
                    run_count=0,
                    error_count=0,
                    last_error=None,
                ))
        except Exception as e:
            logger.warning(f"Failed to get scheduler jobs: {e}")

        return jobs


class HQITOperationsService:
    """Aggregate service for IT Operations dashboard."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.flags = HQFeatureFlagService(db)
        self.health = HQServiceHealthService(db)
        self.deployments = HQDeploymentService(db)

    async def get_dashboard(self) -> ITOperationsDashboard:
        """Get IT Operations dashboard summary."""
        # Service health
        services = await self.health.list_services()
        operational = sum(1 for s in services if s.current_status == "operational")
        degraded = sum(1 for s in services if s.current_status == "degraded")
        outage = sum(1 for s in services if s.current_status == "outage")
        avg_uptime = sum(s.uptime_30d for s in services) / len(services) if services else 100.0

        # Deployments
        deploy_stats = await self.deployments.get_stats()

        # Feature flags
        flags = await self.flags.list_flags()
        enabled_flags = sum(1 for f in flags if f.enabled)

        # Background jobs
        jobs = HQBackgroundJobService.get_jobs()
        running_jobs = sum(1 for j in jobs if j.status == "running")
        failed_jobs = sum(1 for j in jobs if j.status == "failed")

        return ITOperationsDashboard(
            services_operational=operational,
            services_degraded=degraded,
            services_outage=outage,
            overall_uptime=avg_uptime,
            total_deployments_30d=deploy_stats["total_30d"],
            deployment_success_rate=deploy_stats["success_rate"],
            feature_flags_total=len(flags),
            feature_flags_enabled=enabled_flags,
            jobs_running=running_jobs,
            jobs_failed_24h=failed_jobs,
        )
