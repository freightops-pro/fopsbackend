from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
from app.config.db import get_db
from app.models.userModels import (
    ELDCompliance, ELDComplianceCreate, ELDComplianceResponse,
    SAFERData, SAFERDataCreate, SAFERDataResponse,
    InsurancePolicy, InsurancePolicyCreate, InsurancePolicyResponse,
    PermitBook, PermitBookCreate, PermitBookResponse,
    Equipment, Companies, Driver, Users
)
from app.routes.user import get_current_user
import uuid

router = APIRouter(prefix="/api/compliance", tags=["Compliance"])

def get_company_id_from_user(current_user: Users) -> str:
    """Extract company ID from authenticated user"""
    if not current_user.companyid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company"
        )
    return current_user.companyid

# ELD Compliance endpoints
@router.post("/eld-compliance", response_model=ELDComplianceResponse, status_code=status.HTTP_201_CREATED)
def create_eld_compliance(
    compliance: ELDComplianceCreate, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Create new ELD compliance record"""
    try:
        company_id = get_company_id_from_user(current_user)
        db_compliance = ELDCompliance(
            id=str(uuid.uuid4()),
            companyId=company_id,
            driverId=compliance.driverId,
            equipmentId=compliance.equipmentId,
            date=compliance.date,
            totalDrivingTime=compliance.totalDrivingTime,
            totalOnDutyTime=compliance.totalOnDutyTime,
            totalOffDutyTime=compliance.totalOffDutyTime,
            totalSleeperTime=compliance.totalSleeperTime,
            hasViolations=compliance.hasViolations,
            violations=compliance.violations,
            violationTypes=compliance.violationTypes,
            isCompliant=compliance.isCompliant,
            complianceScore=compliance.complianceScore,
            auditStatus=compliance.auditStatus,
            aiAuditResults=compliance.aiAuditResults,
            aiRecommendations=compliance.aiRecommendations,
            aiConfidence=compliance.aiConfidence,
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
            isActive=True
        )
        
        db.add(db_compliance)
        db.commit()
        db.refresh(db_compliance)
        
        return db_compliance
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ELD compliance record: {str(e)}"
        )

@router.get("/eld-compliance", response_model=List[ELDComplianceResponse])
def get_eld_compliance(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Get ELD compliance records"""
    try:
        company_id = get_company_id_from_user(current_user)
        records = db.query(ELDCompliance).filter(
            ELDCompliance.companyId == company_id,
            ELDCompliance.isActive == True
        ).order_by(ELDCompliance.date.desc()).all()
        
        return records
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch ELD compliance records: {str(e)}"
        )

@router.get("/eld-compliance/{compliance_id}", response_model=ELDComplianceResponse)
def get_eld_compliance_record(
    compliance_id: str, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Get specific ELD compliance record"""
    try:
        company_id = get_company_id_from_user(current_user)
        record = db.query(ELDCompliance).filter(
            ELDCompliance.id == compliance_id,
            ELDCompliance.companyId == company_id,
            ELDCompliance.isActive == True
        ).first()
        
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ELD compliance record not found"
            )
        
        return record
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch ELD compliance record: {str(e)}"
        )

@router.put("/eld-compliance/{compliance_id}", response_model=ELDComplianceResponse)
def update_eld_compliance(
    compliance_id: str, 
    compliance_update: ELDComplianceCreate, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Update ELD compliance record"""
    try:
        company_id = get_company_id_from_user(current_user)
        db_compliance = db.query(ELDCompliance).filter(
            ELDCompliance.id == compliance_id,
            ELDCompliance.companyId == company_id,
            ELDCompliance.isActive == True
        ).first()
        
        if not db_compliance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ELD compliance record not found"
            )
        
        # Update fields
        update_data = compliance_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_compliance, field, value)
        
        db_compliance.updatedAt = datetime.utcnow()
        
        db.commit()
        db.refresh(db_compliance)
        
        return db_compliance
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update ELD compliance record: {str(e)}"
        )

@router.delete("/eld-compliance/{compliance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_eld_compliance(
    compliance_id: str, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Soft delete ELD compliance record"""
    try:
        company_id = get_company_id_from_user(current_user)
        db_compliance = db.query(ELDCompliance).filter(
            ELDCompliance.id == compliance_id,
            ELDCompliance.companyId == company_id,
            ELDCompliance.isActive == True
        ).first()
        
        if not db_compliance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ELD compliance record not found"
            )
        
        # Soft delete
        db_compliance.isActive = False
        db_compliance.updatedAt = datetime.utcnow()
        
        db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete ELD compliance record: {str(e)}"
        )

@router.post("/eld-compliance/ai-audit/{compliance_id}")
def run_ai_audit(compliance_id: str, db: Session = Depends(get_db)):
    """Run AI audit on ELD compliance record"""
    try:
        company_id = get_current_user(db)["companyId"]
        compliance = db.query(ELDCompliance).filter(
            ELDCompliance.id == compliance_id,
            ELDCompliance.companyId == company_id,
            ELDCompliance.isActive == True
        ).first()
        
        if not compliance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ELD compliance record not found"
            )
        
        # Simulate AI audit
        ai_results = {
            "analysis": {
                "totalTime": compliance.totalDrivingTime or 0,
                "violations": compliance.violations or [],
                "complianceScore": compliance.complianceScore or 100,
                "riskLevel": "low" if (compliance.complianceScore or 100) > 80 else "medium" if (compliance.complianceScore or 100) > 60 else "high"
            },
            "recommendations": [
                "Ensure proper break periods are taken",
                "Monitor driving time limits",
                "Review sleeper berth usage"
            ],
            "confidence": 0.95
        }
        
        compliance.aiAuditResults = ai_results
        compliance.aiRecommendations = "Ensure proper HOS compliance and take required breaks"
        compliance.aiConfidence = 0.95
        compliance.auditStatus = "reviewed"
        compliance.updatedAt = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": "AI audit completed successfully",
            "results": ai_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run AI audit: {str(e)}"
        )

@router.post("/eld-compliance/export/{compliance_id}")
def export_eld_logs(compliance_id: str, format: str = Query("pdf"), db: Session = Depends(get_db)):
    """Export ELD logs"""
    try:
        company_id = get_current_user(db)["companyId"]
        compliance = db.query(ELDCompliance).filter(
            ELDCompliance.id == compliance_id,
            ELDCompliance.companyId == company_id,
            ELDCompliance.isActive == True
        ).first()
        
        if not compliance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ELD compliance record not found"
            )
        
        export_url = f"/exports/eld-logs/{compliance_id}.{format}"
        
        compliance.exportedAt = datetime.utcnow()
        compliance.exportFormat = format
        compliance.exportUrl = export_url
        compliance.updatedAt = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": f"ELD logs exported successfully in {format.upper()} format",
            "export_url": export_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export ELD logs: {str(e)}"
        )

# SAFER Data endpoints
@router.post("/safer-data", response_model=SAFERDataResponse, status_code=status.HTTP_201_CREATED)
def create_safer_data(safer_data: SAFERDataCreate, db: Session = Depends(get_db)):
    """Create new SAFER data record"""
    try:
        db_safer = SAFERData(
            id=str(uuid.uuid4()),
            companyId=get_current_user(db)["companyId"],
            dotNumber=safer_data.dotNumber,
            legalName=safer_data.legalName,
            dbaName=safer_data.dbaName,
            address=safer_data.address,
            city=safer_data.city,
            state=safer_data.state,
            zipCode=safer_data.zipCode,
            country=safer_data.country,
            safetyRating=safer_data.safetyRating,
            safetyRatingDate=safer_data.safetyRatingDate,
            previousSafetyRating=safer_data.previousSafetyRating,
            totalInspections=safer_data.totalInspections,
            totalInspectionsWithViolations=safer_data.totalInspectionsWithViolations,
            totalViolations=safer_data.totalViolations,
            totalOutOfServiceViolations=safer_data.totalOutOfServiceViolations,
            totalOutOfServiceViolationsPercentage=safer_data.totalOutOfServiceViolationsPercentage,
            totalCrashes=safer_data.totalCrashes,
            fatalCrashes=safer_data.fatalCrashes,
            injuryCrashes=safer_data.injuryCrashes,
            towAwayCrashes=safer_data.towAwayCrashes,
            totalVehicles=safer_data.totalVehicles,
            totalDrivers=safer_data.totalDrivers,
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
            isActive=True
        )
        
        db.add(db_safer)
        db.commit()
        db.refresh(db_safer)
        
        return db_safer
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create SAFER data: {str(e)}"
        )

@router.get("/safer-data", response_model=SAFERDataResponse)
def get_safer_data(db: Session = Depends(get_db)):
    """Get SAFER data for the company"""
    try:
        company_id = get_current_user(db)["companyId"]
        safer_data = db.query(SAFERData).filter(
            SAFERData.companyId == company_id,
            SAFERData.isActive == True
        ).first()
        
        if not safer_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SAFER data not found"
            )
        
        return safer_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch SAFER data: {str(e)}"
        )

@router.post("/safer-data/view-portal")
def view_safer_portal(db: Session = Depends(get_db)):
    """Generate SAFER portal URL"""
    try:
        company_id = get_current_user(db)["companyId"]
        safer_data = db.query(SAFERData).filter(
            SAFERData.companyId == company_id,
            SAFERData.isActive == True
        ).first()
        
        if not safer_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SAFER data not found"
            )
        
        portal_url = f"https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=USDOT&query_string={safer_data.dotNumber}"
        
        safer_data.portalUrl = portal_url
        safer_data.updatedAt = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": "SAFER portal URL generated successfully",
            "portal_url": portal_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SAFER portal URL: {str(e)}"
        )

@router.post("/safer-data/download-report")
def download_safer_report(db: Session = Depends(get_db)):
    """Generate and download SAFER report"""
    try:
        company_id = get_current_user(db)["companyId"]
        safer_data = db.query(SAFERData).filter(
            SAFERData.companyId == company_id,
            SAFERData.isActive == True
        ).first()
        
        if not safer_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SAFER data not found"
            )
        
        report_url = f"/reports/safer/{safer_data.id}.pdf"
        
        safer_data.lastReportGenerated = datetime.utcnow()
        safer_data.reportUrl = report_url
        safer_data.updatedAt = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": "SAFER report generated successfully",
            "report_url": report_url,
            "generated_at": safer_data.lastReportGenerated
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SAFER report: {str(e)}"
        )

# Insurance Policies endpoints
@router.post("/insurance-policies", response_model=InsurancePolicyResponse, status_code=status.HTTP_201_CREATED)
def create_insurance_policy(policy: InsurancePolicyCreate, db: Session = Depends(get_db)):
    """Create new insurance policy"""
    try:
        db_policy = InsurancePolicy(
            id=str(uuid.uuid4()),
            companyId=get_current_user(db)["companyId"],
            policyNumber=policy.policyNumber,
            policyType=policy.policyType,
            insuranceProvider=policy.insuranceProvider,
            agentName=policy.agentName,
            agentPhone=policy.agentPhone,
            agentEmail=policy.agentEmail,
            coverageAmount=policy.coverageAmount,
            deductible=policy.deductible,
            premium=policy.premium,
            paymentFrequency=policy.paymentFrequency,
            effectiveDate=policy.effectiveDate,
            expirationDate=policy.expirationDate,
            renewalDate=policy.renewalDate,
            status=policy.status,
            isRenewed=policy.isRenewed,
            policyDocument=policy.policyDocument,
            certificateOfInsurance=policy.certificateOfInsurance,
            notes=policy.notes,
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
            isActive=True
        )
        
        db.add(db_policy)
        db.commit()
        db.refresh(db_policy)
        
        return db_policy
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create insurance policy: {str(e)}"
        )

@router.get("/insurance-policies", response_model=List[InsurancePolicyResponse])
def get_insurance_policies(db: Session = Depends(get_db)):
    """Get insurance policies"""
    try:
        company_id = get_current_user(db)["companyId"]
        policies = db.query(InsurancePolicy).filter(
            InsurancePolicy.companyId == company_id,
            InsurancePolicy.isActive == True
        ).order_by(InsurancePolicy.expirationDate).all()
        
        return policies
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch insurance policies: {str(e)}"
        )

@router.get("/insurance-policies/renewal-calendar")
def get_renewal_calendar(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db)
):
    """Get insurance policies due for renewal"""
    try:
        company_id = get_current_user(db)["companyId"]
        policies = db.query(InsurancePolicy).filter(
            InsurancePolicy.companyId == company_id,
            InsurancePolicy.isActive == True,
            InsurancePolicy.expirationDate >= start_date,
            InsurancePolicy.expirationDate <= end_date
        ).all()
        
        calendar_events = []
        for policy in policies:
            event = {
                "id": policy.id,
                "title": f"{policy.policyType} - {policy.insuranceProvider}",
                "start": policy.expirationDate.isoformat(),
                "end": policy.expirationDate.isoformat(),
                "policyNumber": policy.policyNumber,
                "status": policy.status,
                "color": get_policy_status_color(policy.status),
                "extendedProps": {
                    "coverageAmount": policy.coverageAmount,
                    "premium": policy.premium,
                    "agentName": policy.agentName,
                    "agentPhone": policy.agentPhone
                }
            }
            calendar_events.append(event)
        
        return calendar_events
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch renewal calendar: {str(e)}"
        )

def get_policy_status_color(status: str) -> str:
    """Get color for policy status"""
    colors = {
        "active": "#10B981",
        "expired": "#EF4444",
        "cancelled": "#6B7280",
        "pending_renewal": "#F59E0B"
    }
    return colors.get(status, "#6B7280")

# Permit Books endpoints
@router.post("/permit-books", response_model=PermitBookResponse, status_code=status.HTTP_201_CREATED)
def create_permit_book(permit: PermitBookCreate, db: Session = Depends(get_db)):
    """Create new permit book entry"""
    try:
        db_permit = PermitBook(
            id=str(uuid.uuid4()),
            companyId=get_current_user(db)["companyId"],
            equipmentId=permit.equipmentId,
            permitNumber=permit.permitNumber,
            permitType=permit.permitType,
            issuingAuthority=permit.issuingAuthority,
            state=permit.state,
            description=permit.description,
            route=permit.route,
            restrictions=permit.restrictions,
            specialConditions=permit.specialConditions,
            issueDate=permit.issueDate,
            expirationDate=permit.expirationDate,
            renewalDate=permit.renewalDate,
            permitFee=permit.permitFee,
            processingFee=permit.processingFee,
            totalFee=permit.totalFee,
            status=permit.status,
            isRenewed=permit.isRenewed,
            permitDocument=permit.permitDocument,
            applicationDocument=permit.applicationDocument,
            notes=permit.notes,
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
            isActive=True
        )
        
        db.add(db_permit)
        db.commit()
        db.refresh(db_permit)
        
        return db_permit
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create permit book entry: {str(e)}"
        )

@router.get("/permit-books", response_model=List[PermitBookResponse])
def get_permit_books(db: Session = Depends(get_db)):
    """Get permit books"""
    try:
        company_id = get_current_user(db)["companyId"]
        permits = db.query(PermitBook).filter(
            PermitBook.companyId == company_id,
            PermitBook.isActive == True
        ).order_by(PermitBook.expirationDate).all()
        
        return permits
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch permit books: {str(e)}"
        )
