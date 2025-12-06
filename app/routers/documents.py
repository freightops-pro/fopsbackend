from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.document import DocumentProcessingJobResponse
from app.services.document_processing import DocumentProcessingService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> DocumentProcessingService:
    return DocumentProcessingService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


async def _user(current_user=Depends(deps.get_current_user)):
    return current_user


@router.post("/ocr", response_model=DocumentProcessingJobResponse)
async def process_document(
    file: UploadFile = File(...),
    load_id: str | None = Form(default=None),
    company_id: str = Depends(_company_id),
    current_user = Depends(_user),
    service: DocumentProcessingService = Depends(_service),
) -> DocumentProcessingJobResponse:
    return await service.process_document(
        company_id=company_id,
        file=file,
        load_id=load_id,
        user_id=current_user.id,
    )

