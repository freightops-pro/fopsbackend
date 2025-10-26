from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, func
from app.config.db import Base


class EmployeeBenefits(Base):
    __tablename__ = "employee_benefits"

    id = Column(String, primary_key=True, index=True)
    employeeId = Column(String, ForeignKey("employees.id"), nullable=False, index=True)

    # Core selections
    effectiveDate = Column(String, nullable=True)
    enrollmentType = Column(String, nullable=True)

    healthPlan = Column(String, nullable=True)
    healthCoverageLevel = Column(String, nullable=True)
    dentalPlan = Column(String, nullable=True)
    dentalCoverageLevel = Column(String, nullable=True)
    visionPlan = Column(String, nullable=True)
    visionCoverageLevel = Column(String, nullable=True)

    lifeInsuranceAmount = Column(String, nullable=True)
    adAndDInsurance = Column(Integer, nullable=True)  # 0/1
    retirement401kContribution = Column(String, nullable=True)
    rothContribution = Column(String, nullable=True)
    healthSavingsAccount = Column(String, nullable=True)
    dependentCareAccount = Column(String, nullable=True)

    voluntaryBenefits = Column(String, nullable=True)  # JSON array string
    lifeEventReason = Column(String, nullable=True)

    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
