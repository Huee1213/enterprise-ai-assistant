import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import init_db, engine
from app.auth import init_admin
import app.agent.graph
from app.routes.health import router as health_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.auth import router as auth_router
from app.routes.agent_config import router as agent_config_router


async def _reindex_registry():
    """Re-index documents from registry into Milvus if missing."""
    registry_path = os.path.join(settings.upload_dir, "registry.json")
    loop = asyncio.get_running_loop()

    entries = await loop.run_in_executor(None, _load_registry, registry_path)

    from app.documents.processor import processor
    from app.vector.store import add_documents
    for entry in entries:
        doc_id = entry.get("id")
        filename = entry.get("filename")
        if not doc_id or not filename:
            continue
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
        file_path = os.path.join(settings.upload_dir, f"{doc_id}.{ext}" if ext else doc_id)
        await loop.run_in_executor(None, _reindex_one, file_path, filename, doc_id, processor, add_documents)


def _load_registry(registry_path: str) -> list:
    import json
    if not os.path.exists(registry_path):
        return []
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _reindex_one(file_path: str, filename: str, doc_id: str, processor, add_documents):
    import os
    if not os.path.exists(file_path):
        return
    try:
        documents = processor.process_file(file_path, filename, doc_id=doc_id)
        add_documents(documents)
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.redis_client import close_redis
    loop = asyncio.get_running_loop()
    await init_db()
    await init_admin()
    avatar_dir = os.path.join(os.path.dirname(__file__), "..", "data", "avatars")
    await loop.run_in_executor(None, os.makedirs, avatar_dir, 0o755, True)
    from fastapi.staticfiles import StaticFiles
    app.mount("/api/files/avatars", StaticFiles(directory=avatar_dir), name="avatars")
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


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "status": "running",
    }
