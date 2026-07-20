import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import init_db, engine
from app.auth import init_admin
import app.agent_graph
from app.routes.health import router as health_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.auth import router as auth_router
from app.routes.agent_config import router as agent_config_router


async def _reindex_registry():
    """Re-index documents from registry into Milvus if missing."""
    registry_path = os.path.join(settings.upload_dir, "registry.json")
    if not os.path.exists(registry_path):
        return
    import json
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    from app.document_processor import processor
    from app.vector_store import add_documents
    for entry in entries:
        doc_id = entry.get("id")
        filename = entry.get("filename")
        if not doc_id or not filename:
            continue
        file_path = os.path.join(settings.upload_dir, f"{doc_id}.{filename.rsplit('.', 1)[-1]}")
        if not os.path.exists(file_path):
            continue
        try:
            documents = processor.process_file(file_path, filename, doc_id=doc_id)
            add_documents(documents)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.redis_client import close_redis
    await init_db()
    await init_admin()
    await _reindex_registry()
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Enterprise AI Knowledge Assistant with LangGraph Agent",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(agent_config_router)

import os
avatar_dir = os.path.join(os.path.dirname(__file__), "..", "data", "avatars")
os.makedirs(avatar_dir, exist_ok=True)
app.mount("/api/files/avatars", StaticFiles(directory=avatar_dir), name="avatars")


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "status": "running",
    }
