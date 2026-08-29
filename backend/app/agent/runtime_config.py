import json
from functools import lru_cache
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.database import DB_URL
from app.config import settings

# Dedicated engine for config reads issued from FOREIGN event loops (worker
# threads such as vector indexing / tool execution create their own loop via
# `asyncio.new_event_loop()`). asyncpg connections are bound to the loop that
# created them; if those connections were returned to the shared engine pool,
# the main loop would later reuse/terminate them and crash with
# "Task got Future attached to a different loop" /
# "InternalClientError: unknown protocol state 3" on every startup.
# NullPool opens a fresh connection per call and closes it — never shared.
_cfg_engine = create_async_engine(DB_URL, poolclass=NullPool)
_cfg_sessionmaker = async_sessionmaker(_cfg_engine, expire_on_commit=False)


@lru_cache(maxsize=1)
def _cached_str(key: str) -> str:
    """LRU cache returns the config value for the current session."""
    return key


def get_runtime_key() -> str:
    """Return a cache key that changes when config is updated (based on max id)."""
    return "config_v0"


def _load_overrides_sync() -> dict:
    """Sync helper to load overrides from DB. Called in thread pool."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_load_overrides_async())
    finally:
        loop.close()


async def _load_overrides_async() -> dict:
    try:
        async with _cfg_sessionmaker() as db:
            result = await db.execute(
                select(text("config_json")).select_from(text("agent_config")).order_by(text("id DESC")).limit(1)
            )
            row = result.scalar_one_or_none()
            if row:
                return json.loads(row)
    except Exception:
        pass
    return {}


async def get_effective_config() -> dict:
    """Return merged config: env defaults + DB overrides."""
    import asyncio
    overrides = await _load_overrides_async()
    effective = {
        "llm_model": settings.llm_model,
        "llm_temperature": settings.llm_temperature,
        "llm_max_tokens": settings.llm_max_tokens,
        "llm_api_key": settings.llm_api_key or "",
        "llm_api_base": settings.llm_api_base or "",
        "embedding_model": settings.embedding_model,
        "embedding_api_key": settings.embedding_api_key or "",
        "embedding_api_base": settings.embedding_api_base or "",
        "embedding_download_provider": settings.embedding_download_provider,
        "top_k": settings.top_k,
        "score_threshold": settings.score_threshold,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "system_prompt": "",
        "enable_web_search": True,
        "enable_knowledge_search": True,
        "enable_summarize": True,
        "enable_time_tool": True,
        "max_tool_rounds": 5,
    }
    effective.update(overrides)
    return effective


def get_effective_config_sync() -> dict:
    """Sync read of the effective config, safe to call from worker threads.

    Uses the dedicated NullPool engine (see _load_overrides_async) so it never
    touches the shared async engine's pool from a foreign event loop.
    """
    import asyncio as _a
    try:
        _a.get_running_loop()
    except RuntimeError:
        loop = _a.new_event_loop()
        try:
            return loop.run_until_complete(get_effective_config())
        finally:
            loop.close()
    # Called from a running loop — env defaults only (should not happen).
    return {}
