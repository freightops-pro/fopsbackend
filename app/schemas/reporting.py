from datetime import date
from typing import Optional

from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    total_loads: int
    loads_in_progress: int
    total_invoices: int
    accounts_active: int
    last_automation_run: Optional[date] = None

