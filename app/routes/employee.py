from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import csv
import io
import json
from datetime import datetime
from app.config.db import get_db
from app.schema.employeeSchema import EmployeeCreate, EmployeeOut, EmployeeStats, EmployeeUpdate
from app.services.employee_service import create_employee, list_employees, employee_stats, get_employee, update_employee, delete_employee
from app.models.employee import Employee

router = APIRouter(prefix="/api/hr/employees", tags=["HR - Employees"])


@router.get("", response_model=List[EmployeeOut])
def get_employees(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_employees(db, skip=skip, limit=limit)


@router.post("", response_model=EmployeeOut, status_code=201)
def add_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    if payload.email:
        existing = db.query(Employee).filter(Employee.email == payload.email.lower().strip()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")
    return create_employee(db, payload)


@router.get("/stats", response_model=EmployeeStats)
def get_employee_stats(db: Session = Depends(get_db)):
    return employee_stats(db)


@router.get("/export")
def export_employees(db: Session = Depends(get_db)):
    """Export all employees as CSV."""
    employees = db.query(Employee).order_by(Employee.createdAt.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    headers = [
        "name","position","department","status","hireDate","email","phone","cdlClass","experienceYears","location","profileInitials","id"
    ]
    writer.writerow(headers)
    for e in employees:
        writer.writerow([
            e.name or "",
            e.position or "",
            e.department or "",
            e.status or "",
            (e.hireDate.isoformat() if isinstance(e.hireDate, datetime) else (e.hireDate or "")),
            e.email or "",
            e.phone or "",
            e.cdlClass or "",
            e.experienceYears or 0,
            e.location or "",
            e.profileInitials or "",
            e.id,
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=employees.csv"}
    )


def _normalize_row(row: Dict[str, Any], mapping: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    # If mapping provided: mapping[fieldName] = csvHeader
    known_fields = {"name","position","department","status","hireDate","email","phone","cdlClass","experienceYears","location","profileInitials","companyId"}
    normalized = {}
    if mapping:
        for field, header in mapping.items():
            if field in known_fields:
                normalized[field] = row.get(header)
    else:
        # best-effort by matching lower-cased keys
        alias = {
            "hire date": "hireDate",
            "experience": "experienceYears",
            "experience_years": "experienceYears",
            "cdl": "cdlClass",
        }
        for k, v in row.items():
            key = k.strip()
            low = key.lower().replace(" ", "").replace("-", "_")
            field = None
            if key in known_fields:
                field = key
            elif low in [f.lower() for f in known_fields]:
                # map if exact lower-case match
                for f in known_fields:
                    if f.lower() == low:
                        field = f
                        break
            elif key.lower() in alias:
                field = alias[key.lower()]
            if field:
                normalized[field] = v
    # type conversions
    if "experienceYears" in normalized and normalized["experienceYears"] not in (None, ""):
        try:
            normalized["experienceYears"] = int(float(str(normalized["experienceYears"]).strip()))
        except Exception:
            normalized["experienceYears"] = 0
    if "hireDate" in normalized and normalized["hireDate"]:
        try:
            val = str(normalized["hireDate"]).strip()
            normalized["hireDate"] = datetime.fromisoformat(val)
        except Exception:
            normalized["hireDate"] = None
    if "email" in normalized and normalized["email"]:
        normalized["email"] = str(normalized["email"]).lower().strip()
    return normalized


@router.post("/import-file")
def import_employees_file(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None),
    upsertByEmail: bool = Form(True),
    db: Session = Depends(get_db),
):
    """Import employees from a CSV file (multipart). Optional mapping JSON maps field->csvHeader."""
    content = file.file.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    mapping_dict = json.loads(mapping) if mapping else None
    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    for idx, row in enumerate(reader, start=1):
        data = _normalize_row(row, mapping_dict)
        name = (data.get("name") or "").strip()
        if not name:
            skipped += 1
            continue
        email = data.get("email")
        try:
            if upsertByEmail and email:
                existing = db.query(Employee).filter(Employee.email == email).first()
                if existing:
                    # update existing
                    for k, v in data.items():
                        if v is not None and hasattr(existing, k):
                            setattr(existing, k, v)
                    existing.updatedAt = datetime.utcnow()
                    db.add(existing)
                    updated += 1
                    continue
            # create new
            payload = EmployeeCreate(**{k: v for k, v in data.items() if v is not None})
            emp = create_employee(db, payload)
            if emp:
                created += 1
            else:
                skipped += 1
        except Exception as ex:
            errors.append(f"row {idx}: {ex}")
            skipped += 1
    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}


@router.post("/import")
def import_employees_json(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """Import employees from normalized JSON: { employees: EmployeeCreate[], upsertByEmail?: bool }"""
    employees = payload.get("employees") or []
    upsert = payload.get("upsertByEmail", True)
    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    for idx, item in enumerate(employees, start=1):
        try:
            name = (item.get("name") or "").strip()
            if not name:
                skipped += 1
                continue
            email = item.get("email")
            if upsert and email:
                existing = db.query(Employee).filter(Employee.email == email.lower().strip()).first()
                if existing:
                    for k, v in item.items():
                        if v is not None and hasattr(existing, k):
                            setattr(existing, k, v)
                    existing.updatedAt = datetime.utcnow()
                    db.add(existing)
                    updated += 1
                    continue
            payload_obj = EmployeeCreate(**item)
            emp = create_employee(db, payload_obj)
            if emp:
                created += 1
            else:
                skipped += 1
        except Exception as ex:
            errors.append(f"row {idx}: {ex}")
            skipped += 1
    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee_detail(employee_id: str = Path(...), db: Session = Depends(get_db)):
    emp = get_employee(db, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


@router.patch("/{employee_id}", response_model=EmployeeOut)
@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee_route(employee_id: str, payload: EmployeeUpdate, db: Session = Depends(get_db)):
    try:
        emp = update_employee(db, employee_id, payload.dict(exclude_unset=True))
        return emp
    except ValueError:
        raise HTTPException(status_code=404, detail="Employee not found")


@router.delete("/{employee_id}", status_code=204)
def delete_employee_route(employee_id: str, db: Session = Depends(get_db)):
    ok = delete_employee(db, employee_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Employee not found")
    return None

