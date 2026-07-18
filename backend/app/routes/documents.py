import os
import uuid
import shutil
from datetime import datetime
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from app.models import DocumentInfo, UploadResponse, BulkUploadResponse
from app.config import settings
from app.document_processor import processor
from app.vector_store import add_documents, get_vector_store
from app.document_registry import register_document, list_documents, delete_document as registry_delete
from app.auth import require_admin

router = APIRouter(prefix="/api/documents", tags=["Documents"])


class ChunkInfo(BaseModel):
    index: int
    content: str
    source: str
    doc_id: str


class DocDetailResponse(BaseModel):
    id: str
    filename: str
    size: int
    content_type: str
    uploaded_at: str
    chunk_count: int
    original_content: str
    chunks: List[ChunkInfo]


def _get_file_path(doc_id: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1]
    return os.path.join(settings.upload_dir, f"{doc_id}{ext}")


def _read_original_content(doc_id: str, filename: str) -> str:
    file_path = _get_file_path(doc_id, filename)
    if not os.path.exists(file_path):
        return "(文件已丢失)"
    try:
        return processor.read_file(file_path) or "(无法读取文件内容)"
    except Exception as e:
        return f"(读取失败: {str(e)})"


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), admin_user: dict = Depends(require_admin)):
    ext = os.path.splitext(file.filename or "unknown")[1].lower()
    if ext not in processor.SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}。支持的类型: {processor.SUPPORTED_EXTENSIONS}")

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
        chunk_texts = [d.page_content for d in documents]
        cc = len(chunk_texts)

        register_document(doc_id=doc_id, filename=file.filename or safe_name, size=file_size, content_type=ext.lstrip("."), chunk_count=cc, chunk_texts=chunk_texts)

        return UploadResponse(id=doc_id, filename=file.filename or safe_name, status="success", message=f"已处理 {cc} 个文本块: {file.filename}")
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


async def _process_and_register(file: UploadFile) -> UploadResponse:
    """Process a single uploaded file and return result."""
    ext = os.path.splitext(file.filename or "unknown")[1].lower()
    if ext not in processor.SUPPORTED_EXTENSIONS:
        return UploadResponse(id="", filename=file.filename or "unknown", status="error", message=f"不支持的文件类型: {ext}")

    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}{ext}"
    file_path = os.path.join(settings.upload_dir, safe_name)
    os.makedirs(settings.upload_dir, exist_ok=True)

    try:
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
    except Exception:
        file_size = 0

    with open(file_path, "wb") as f:
        file.file.seek(0)
        shutil.copyfileobj(file.file, f)

    try:
        documents = processor.process_file(file_path, file.filename or safe_name)
        ids = add_documents(documents)
        chunk_texts = [d.page_content for d in documents]
        cc = len(chunk_texts)
        register_document(doc_id=doc_id, filename=file.filename or safe_name, size=file_size, content_type=ext.lstrip("."), chunk_count=cc, chunk_texts=chunk_texts)
        return UploadResponse(id=doc_id, filename=file.filename or safe_name, status="success", message=f"已处理 {cc} 个文本块")
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return UploadResponse(id="", filename=file.filename or safe_name, status="error", message=str(e)[:100])


@router.post("/upload-bulk", response_model=BulkUploadResponse)
async def upload_documents_bulk(files: List[UploadFile] = File(...), admin_user: dict = Depends(require_admin)):
    results = []
    for f in files:
        r = await _process_and_register(f)
        results.append(r)
    success = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "error")
    return BulkUploadResponse(total=len(results), success=success, failed=failed, results=results)


@router.get("/list", response_model=List[DocumentInfo])
async def list_documents_route(admin_user: dict = Depends(require_admin)):
    try:
        return list_documents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{doc_id}", response_model=DocDetailResponse)
async def get_document_detail(doc_id: str, admin_user: dict = Depends(require_admin)):
    docs = list_documents()
    doc = next((d for d in docs if d.id == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    original = _read_original_content(doc_id, doc.filename)

    chunks = []
    try:
        import json as _json
        registry_path = os.path.join(settings.upload_dir, "registry.json")
        if os.path.exists(registry_path):
            with open(registry_path, "r", encoding="utf-8") as f:
                entries = _json.load(f)
            for entry in entries:
                if entry["id"] == doc_id:
                    chunks_meta = entry.get("chunks", [])
                    if chunks_meta:
                        for c in chunks_meta:
                            chunks.append(ChunkInfo(index=c["index"], content=c["content"], source=doc.filename, doc_id=doc_id))
                        break
    except Exception:
        pass

    if not chunks:
        try:
            from app.vector_store import similarity_search
            results = similarity_search("document content", k=100)
            seen = set()
            for r in results:
                if r.metadata.get("doc_id") == doc_id and r.page_content not in seen:
                    idx = r.metadata.get("chunk_index", len(chunks))
                    chunks.append(ChunkInfo(index=idx, content=r.page_content, source=doc.filename, doc_id=doc_id))
                    seen.add(r.page_content)
            chunks.sort(key=lambda c: c.index)
        except Exception:
            pass

    if not chunks:
        try:
            file_path = _get_file_path(doc_id, doc.filename)
            if os.path.exists(file_path):
                from app.document_processor import processor as doc_proc
                docs = doc_proc.process_file(file_path, doc.filename)
                for i, d in enumerate(docs):
                    chunks.append(ChunkInfo(index=i, content=d.page_content, source=doc.filename, doc_id=doc_id))
        except Exception:
            pass

    return DocDetailResponse(
        id=doc.id, filename=doc.filename, size=doc.size,
        content_type=doc.content_type, uploaded_at=doc.uploaded_at.isoformat() if isinstance(doc.uploaded_at, datetime) else str(doc.uploaded_at),
        chunk_count=doc.chunk_count, original_content=original, chunks=chunks,
    )


@router.get("/{doc_id}/file")
async def get_document_file(
    doc_id: str,
    token: str = None,
    admin_user: dict = Depends(require_admin),
):
    docs = list_documents()
    doc = next((d for d in docs if d.id == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    file_path = _get_file_path(doc_id, doc.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件已丢失")
    from fastapi.responses import FileResponse
    return FileResponse(file_path, filename=doc.filename)


@router.delete("/{doc_id}", response_model=dict)
async def delete_document_route(doc_id: str, admin_user: dict = Depends(require_admin)):
    try:
        from app.vector_store import delete_document as vector_delete
        vector_delete(doc_id)
        registry_delete(doc_id)
        return {"status": "deleted", "id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
