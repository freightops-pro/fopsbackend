from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import uuid
import os
from typing import List, Optional, Dict, Any

from app.models.document import Document
from app.schema.documentSchema import DocumentCreate, DocumentUpdate


def _ensure_document_schema(db: Session) -> None:
    """Self-heal: ensure new columns exist without full migrations."""
    try:
        dialect = db.bind.dialect.name if db.bind else ""
        if dialect == "postgresql":
            db.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS expiryDate TIMESTAMP"))
            db.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS details JSON"))
            db.commit()
        elif dialect == "sqlite":
            try:
                for stmt in [
                    "ALTER TABLE documents ADD COLUMN expiryDate TEXT",
                    "ALTER TABLE documents ADD COLUMN details TEXT",
                ]:
                    try:
                        db.execute(text(stmt))
                    except Exception:
                        db.rollback()
                db.commit()
            except Exception:
                db.rollback()
    except Exception:
        db.rollback()


def list_documents(db: Session, company_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Document]:
    _ensure_document_schema(db)
    q = db.query(Document)
    if company_id:
        q = q.filter(Document.companyId == company_id)
    return q.order_by(Document.createdAt.desc()).offset(skip).limit(limit).all()


def get_document(db: Session, document_id: str) -> Optional[Document]:
    return db.query(Document).filter(Document.id == document_id).first()


def create_document(db: Session, payload: DocumentCreate) -> Document:
    _ensure_document_schema(db)
    new_id = str(uuid.uuid4())
    
    # Create uploads directory if it doesn't exist
    upload_dir = "uploads/documents"
    os.makedirs(upload_dir, exist_ok=True)
    
    document = Document(
        id=new_id,
        companyId=payload.companyId,
        name=payload.name,
        type=payload.type,
        category=payload.category,
        description=payload.description,
        fileName=payload.fileName,
        fileSize=payload.fileSize,
        fileType=payload.fileType,
        filePath=payload.filePath,
        employeeId=payload.employeeId,
        employeeName=payload.employeeName,
        status=payload.status,
        expiryDate=payload.expiryDate,
        details=payload.details,
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def update_document(db: Session, document_id: str, payload: DocumentUpdate) -> Document:
    _ensure_document_schema(db)
    document = get_document(db, document_id)
    if not document:
        raise ValueError("Document not found")
    
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if hasattr(document, k):
            setattr(document, k, v)
    
    document.updatedAt = datetime.utcnow()
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document_id: str) -> bool:
    _ensure_document_schema(db)
    document = get_document(db, document_id)
    if not document:
        return False
    
    # Delete the actual file if it exists
    if document.filePath and os.path.exists(document.filePath):
        try:
            os.remove(document.filePath)
        except Exception:
            pass  # Continue even if file deletion fails
    
    db.delete(document)
    db.commit()
    return True


def get_documents_by_employee(db: Session, employee_id: str, company_id: Optional[str] = None) -> List[Document]:
    _ensure_document_schema(db)
    q = db.query(Document).filter(Document.employeeId == employee_id)
    if company_id:
        q = q.filter(Document.companyId == company_id)
    return q.order_by(Document.createdAt.desc()).all()


def get_documents_by_category(db: Session, category: str, company_id: Optional[str] = None) -> List[Document]:
    _ensure_document_schema(db)
    q = db.query(Document).filter(Document.category == category)
    if company_id:
        q = q.filter(Document.companyId == company_id)
    return q.order_by(Document.createdAt.desc()).all() 