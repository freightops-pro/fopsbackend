from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation import AutomationRule
from app.models.driver import Driver, DriverIncident
from app.models.fuel import JurisdictionRollup
from app.models.equipment import Equipment, EquipmentMaintenanceForecast
from app.models.notification import NotificationLog
from app.services.notifications import NotificationSender
from app.services.automation import AutomationService


class AutomationEvaluationResult:
    def __init__(self) -> None:
        self.sent: List[Tuple[str, str]] = []
        self.skipped: List[str] = []
        self.failed: List[Tuple[str, str]] = []


class AutomationEvaluator:
    def __init__(self, db: AsyncSession, channels: Dict[str, NotificationSender]) -> None:
        self.db = db
        self.channels = channels

    async def evaluate_company(self, company_id: str, service: AutomationService | None = None) -> AutomationEvaluationResult:
        result = AutomationEvaluationResult()
        automation_service = service or AutomationService(self.db)
        rules = await automation_service.list_rules(company_id)
        for rule in rules:
            recipients = await self._resolve_recipients(company_id, rule)
            if not recipients:
                result.skipped.append(rule.id)
                continue
            body = self._generate_body(rule)
            subject = f"[FreightOps] {rule.name}"

            for recipient in recipients:
                for channel in rule.channels:
                    sender = self.channels.get(channel)
                    if not sender:
                        continue
                    outcome = await sender.send(recipient, subject, body)
                    await self._log_delivery(company_id, rule, channel, recipient, outcome.success, outcome.detail)
                    if outcome.success:
                        result.sent.append((rule.id, channel))
                    else:
                        result.failed.append((rule.id, channel))

            rule.last_triggered_at = datetime.utcnow()
        await self.db.commit()
        return result

    def _generate_body(self, rule: AutomationRule) -> str:
        context = getattr(rule, "_context", {})
        if rule.trigger == "maintenance_overdue":
            alerts = context.get("maintenance") or []
            if alerts:
                lines = [f"{len(alerts)} maintenance item(s) require attention."]
                for alert in alerts[:5]:
                    projected_date = alert.get("projected_service_date")
                    date_hint = projected_date.isoformat() if projected_date else "unscheduled"
                    risk = int((alert.get("risk_score") or 0.0) * 100)
                    lines.append(
                        f"- {alert['unit_number']} · {alert['service_type']} · {alert['status']} (risk {risk}%) · {date_hint}"
                    )
                if len(alerts) > 5:
                    lines.append(f"...and {len(alerts) - 5} more.")
                return "\n".join(lines)
        return f"Automation '{rule.name}' triggered for {rule.trigger}"

    async def _resolve_recipients(self, company_id: str, rule: AutomationRule) -> List[str]:
        today = date.today()
        lead_days = rule.lead_time_days or 0
        window_end = today + timedelta(days=lead_days)

        if rule.trigger == "cdl_expiring":
            return await self._drivers_with_expiration(company_id, "cdl_expiration", today, window_end)
        if rule.trigger == "medical_card_expiring":
            return await self._drivers_with_expiration(company_id, "medical_card_expiration", today, window_end)
        if rule.trigger == "incident_high_severity":
            recent = await self._recent_incidents(company_id)
            return recent if recent else rule.recipients
        if rule.trigger == "ifta_tax_threshold" and rule.threshold_value is not None:
            meets = await self._jurisdiction_threshold(company_id, rule.threshold_value)
            return rule.recipients if meets else []
        if rule.trigger == "maintenance_overdue":
            alerts = await self._maintenance_due_forecasts(
                company_id=company_id,
                lead_days=rule.lead_time_days or 0,
                risk_threshold=rule.threshold_value,
            )
            if not alerts:
                return []
            setattr(rule, "_context", {"maintenance": alerts})
            return rule.recipients
        # Placeholder for permit/maintenance triggers
        return rule.recipients

    async def _drivers_with_expiration(
        self,
        company_id: str,
        column: str,
        start: date,
        end: date,
    ) -> List[str]:
        exp_column = getattr(Driver, column)
        result = await self.db.execute(
            select(Driver.email)
            .where(
                Driver.company_id == company_id,
                exp_column >= start,
                exp_column <= end,
                Driver.email.isnot(None),
            )
        )
        emails = [email for email in result.scalars().all() if email]
        return emails or []

    async def _recent_incidents(self, company_id: str) -> List[str]:
        cutoff = datetime.utcnow() - timedelta(days=1)
        result = await self.db.execute(
            select(Driver.email)
            .join(DriverIncident, DriverIncident.driver_id == Driver.id)
            .where(
                Driver.company_id == company_id,
                DriverIncident.severity == "CRITICAL",
                DriverIncident.occurred_at >= cutoff,
                Driver.email.isnot(None),
            )
        )
        emails = [email for email in result.scalars().all() if email]
        return emails

    async def _jurisdiction_threshold(self, company_id: str, threshold: float) -> bool:
        result = await self.db.execute(
            select(func.coalesce(func.sum(JurisdictionRollup.tax_due), 0)).where(
                JurisdictionRollup.company_id == company_id
            )
        )
        total_tax = result.scalar_one()
        return float(total_tax or 0) >= threshold

    async def _maintenance_due_forecasts(
        self,
        company_id: str,
        lead_days: int,
        risk_threshold: float | None,
    ) -> List[Dict[str, object]]:
        today = date.today()
        window_end = today + timedelta(days=lead_days) if lead_days > 0 else today

        status_filters = [EquipmentMaintenanceForecast.status == "OVERDUE"]
        if lead_days > 0:
            status_filters.append(
                and_(
                    EquipmentMaintenanceForecast.status == "DUE_SOON",
                    EquipmentMaintenanceForecast.projected_service_date.isnot(None),
                    EquipmentMaintenanceForecast.projected_service_date <= window_end,
                )
            )

        stmt = (
            select(
                EquipmentMaintenanceForecast,
                Equipment.unit_number,
                Equipment.equipment_type,
            )
            .join(Equipment, EquipmentMaintenanceForecast.equipment_id == Equipment.id)
            .where(
                EquipmentMaintenanceForecast.company_id == company_id,
                or_(*status_filters),
            )
        )

        if risk_threshold is not None:
            stmt = stmt.where(EquipmentMaintenanceForecast.risk_score >= float(risk_threshold))

        result = await self.db.execute(stmt)
        alerts: List[Dict[str, object]] = []
        for forecast, unit_number, equipment_type in result.all():
            alerts.append(
                {
                    "equipment_id": forecast.equipment_id,
                    "unit_number": unit_number or "",
                    "equipment_type": equipment_type or "equipment",
                    "service_type": forecast.service_type,
                    "status": forecast.status,
                    "projected_service_date": forecast.projected_service_date,
                    "projected_service_mileage": forecast.projected_service_mileage,
                    "risk_score": float(forecast.risk_score or 0.0),
                }
            )
        return alerts

    async def _log_delivery(
        self,
        company_id: str,
        rule: AutomationRule,
        channel: str,
        recipient: str,
        success: bool,
        detail: str,
    ) -> None:
        log = NotificationLog(
            id=str(uuid.uuid4()),
            company_id=company_id,
            rule_id=rule.id,
            channel=channel,
            recipient=recipient,
            status="sent" if success else "error",
            detail=detail,
        )
        self.db.add(log)

