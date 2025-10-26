from sqlalchemy import Column, Integer, String, Date, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.config.db import Base

class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    id = Column(Integer, primary_key=True, index=True)
    pay_period_start = Column(Date, nullable=False)
    pay_period_end = Column(Date, nullable=False)
    pay_date = Column(Date, nullable=False)
    payroll_type = Column(String, nullable=False, default="regular")
    departments = Column(Text, nullable=False)  # comma-separated list
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="Draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    entries = relationship("PayrollEntry", back_populates="run", cascade="all,delete-orphan")

class PayrollEntry(Base):
    __tablename__ = "payroll_entries"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("payroll_runs.id"), nullable=False, index=True)
    employee_id = Column(String, nullable=False, index=True)
    employee_name = Column(String, nullable=False)
    position = Column(String, nullable=True)
    department = Column(String, nullable=True)
    hourly_rate = Column(Float, default=25.0)
    regular_hours = Column(Float, default=0)
    overtime_hours = Column(Float, default=0)
    bonus_amount = Column(Float, default=0)
    mileage = Column(Float, default=0)
    per_diem = Column(Float, default=0)
    gross_pay = Column(Float, default=0)
    federal_tax = Column(Float, default=0)
    state_tax = Column(Float, default=0)
    fica_tax = Column(Float, default=0)
    health_insurance = Column(Float, default=0)
    retirement_401k = Column(Float, default=0)
    other_deductions = Column(Float, default=0)
    total_deductions = Column(Float, default=0)
    net_pay = Column(Float, default=0)
    status = Column(String, default="Pending")
    pay_period = Column(String, nullable=True)
    has_w2 = Column(Integer, default=1)  # 1 true 0 false
    has_1099 = Column(Integer, default=0)
    run = relationship("PayrollRun", back_populates="entries")

class OvertimeApproval(Base):
    __tablename__ = "overtime_approvals"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, nullable=False, index=True)
    overtime_hours = Column(Float, nullable=False)
    overtime_rate = Column(Float, nullable=False)
    approval_reason = Column(Text, nullable=False)
    week_ending = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class BonusPayment(Base):
    __tablename__ = "bonus_payments"
    id = Column(Integer, primary_key=True, index=True)
    bonus_type = Column(String, nullable=False)
    tax_withholding = Column(String, nullable=False)
    bonus_amount = Column(Float, nullable=False)
    bonus_reason = Column(Text, nullable=False)
    effective_date = Column(Date, nullable=False)
    employee_ids_json = Column(Text, nullable=False)  # JSON array string
    created_at = Column(DateTime, default=datetime.utcnow)

class DriverSettlement(Base):
    __tablename__ = "driver_settlements"
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(String, nullable=False, index=True)
    settlement_period = Column(String, nullable=False)
    total_miles = Column(Float, nullable=False)
    mileage_rate = Column(Float, nullable=False)
    detention_hours = Column(Float, nullable=True)
    detention_rate = Column(Float, nullable=True)
    fuel_surcharge = Column(Float, nullable=True)
    other_deductions = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
