from fastapi import APIRouter, Depends, HTTPException, Query, Path, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
from datetime import datetime

from app.config.db import get_db
from app.schema.documentSchema import DocumentCreate, DocumentOut, DocumentUpdate
from app.services.document_service import (
    list_documents,
    get_document,
    create_document,
    update_document,
    delete_document,
    get_documents_by_employee,
    get_documents_by_category,
)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.get("", response_model=List[DocumentOut])
def get_documents(
    companyId: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_documents(db, company_id=companyId, skip=skip, limit=limit)


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    name: str = Form(...),
    type: str = Form(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    employeeId: Optional[str] = Form(None),
    employeeName: Optional[str] = Form(None),
    companyId: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Validate file type
    allowed_types = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.jpg', '.jpeg', '.png']
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_types:
        raise HTTPException(status_code=400, detail=f"File type {file_ext} not allowed")
    
    # Create uploads directory
    upload_dir = "uploads/documents"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{file_id}{file_ext}"
    file_path = os.path.join(upload_dir, filename)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Create document record
    document_data = DocumentCreate(
        companyId=companyId,
        name=name,
        type=type,
        category=category,
        description=description,
        fileName=file.filename,
        fileSize=len(content),
        fileType=file_ext[1:].upper(),
        filePath=file_path,
        employeeId=employeeId,
        employeeName=employeeName,
    )
    
    return create_document(db, document_data)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document_detail(document_id: str = Path(...), db: Session = Depends(get_db)):
    document = get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/download")
def download_document(document_id: str = Path(...), db: Session = Depends(get_db)):
    document = get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not document.filePath or not os.path.exists(document.filePath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        document.filePath,
        filename=document.fileName,
        media_type='application/octet-stream'
    )


@router.patch("/{document_id}", response_model=DocumentOut)
@router.put("/{document_id}", response_model=DocumentOut)
def update_document_route(document_id: str, payload: DocumentUpdate, db: Session = Depends(get_db)):
    try:
        document = update_document(db, document_id, payload)
        return document
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")


@router.delete("/{document_id}", status_code=204)
def delete_document_route(document_id: str, db: Session = Depends(get_db)):
    ok = delete_document(db, document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return None


@router.get("/employee/{employee_id}", response_model=List[DocumentOut])
def get_employee_documents(
    employee_id: str = Path(...),
    companyId: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return get_documents_by_employee(db, employee_id, company_id)


@router.get("/category/{category}", response_model=List[DocumentOut])
def get_category_documents(
    category: str = Path(...),
    companyId: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return get_documents_by_category(db, category, company_id) 