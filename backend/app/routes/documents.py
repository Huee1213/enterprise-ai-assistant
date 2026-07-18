import os
import uuid
import shutil
from datetime import datetime
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.models import DocumentInfo, UploadResponse
from app.config import settings
from app.document_processor import processor
from app.vector_store import add_documents
from app.document_registry import register_document, list_documents, delete_document as registry_delete
from app.auth import require_admin

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), admin_user: dict = Depends(require_admin)):
    ext = os.path.splitext(file.filename or "unknown")[1].lower()
    if ext not in processor.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}。支持的类型: {processor.SUPPORTED_EXTENSIONS}",
        )

    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}{ext}"
    file_path = os.path.join(settings.upload_dir, safe_name)
    os.makedirs(settings.upload_dir, exist_ok=True)

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        documents = processor.process_file(file_path, file.filename or safe_name)
        ids = add_documents(documents)
        chunk_count = len(documents)

        register_document(
            doc_id=doc_id,
            filename=file.filename or safe_name,
            size=file_size,
            content_type=ext.lstrip("."),
            chunk_count=chunk_count,
        )

        return UploadResponse(
            id=doc_id,
            filename=file.filename or safe_name,
            status="success",
            message=f"已处理 {chunk_count} 个文本块: {file.filename}",
        )
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=List[DocumentInfo])
async def list_documents_route(admin_user: dict = Depends(require_admin)):
    try:
        return list_documents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{doc_id}", response_model=dict)
async def delete_document_route(doc_id: str, admin_user: dict = Depends(require_admin)):
    try:
        from app.vector_store import delete_document as vector_delete
        vector_delete(doc_id)
        registry_delete(doc_id)
        return {"status": "deleted", "id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
