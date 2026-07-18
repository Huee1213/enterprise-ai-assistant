import json
import os
from datetime import datetime
from typing import List, Optional
from app.models import DocumentInfo
from app.config import settings

REGISTRY_PATH = os.path.join(settings.upload_dir, "registry.json")


def _load_registry() -> list:
    if not os.path.exists(REGISTRY_PATH):
        return []
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_registry(registry: list) -> None:
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def register_document(doc_id: str, filename: str, size: int, content_type: str, chunk_count: int) -> DocumentInfo:
    registry = _load_registry()
    now = datetime.now().isoformat()
    entry = {
        "id": doc_id,
        "filename": filename,
        "size": size,
        "content_type": content_type,
        "uploaded_at": now,
        "chunk_count": chunk_count,
    }
    registry.append(entry)
    _save_registry(registry)
    return DocumentInfo(**entry)


def list_documents() -> List[DocumentInfo]:
    return [DocumentInfo(**e) for e in _load_registry()]


def delete_document(doc_id: str) -> bool:
    registry = _load_registry()
    filtered = [e for e in registry if e["id"] != doc_id]
    if len(filtered) == len(registry):
        return False
    _save_registry(filtered)
    return True
