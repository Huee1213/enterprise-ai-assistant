import json
import asyncio
import logging
import httpx
import queue
import threading
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder

from app.database import get_db, AgentConfig
from app.config import settings
from app.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agent Config"])

DEFAULT_CONFIG = {
    "llm_provider": settings.llm_provider,
    "llm_model": settings.llm_model,
    "llm_api_key": settings.llm_api_key,
    "llm_api_base": settings.llm_api_base,
    "llm_temperature": settings.llm_temperature,
    "llm_max_tokens": settings.llm_max_tokens,
    "embedding_provider": "local" if settings.embedding_model.startswith("local/") else settings.llm_provider,
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

BEST_PRACTICES = {
    "llm": {
        "title": "LLM 模型配置",
        "tips": [
            "建议 temperature 设置在 0.1-0.3 之间以保证回答稳定性，创意类任务可适当提高至 0.5-0.7",
            "max_tokens 建议 2048-4096，过长会增加响应延迟和成本",
            "推荐使用延迟较低的模型（如 gpt-4o-mini、claude-sonnet）以获得更好的用户体验",
            "API Base 需与模型提供商匹配，使用 OpenRouter 时注意模型的上下文长度限制",
        ],
    },
    "embedding": {
        "title": "向量嵌入配置",
        "tips": [
            "本地嵌入模型（local/ 前缀）无需 API Key，适合离线场景",
            "BAAI/bge-small-en-v1.5 是轻量级嵌入模型，768维，适合大多数场景",
            "若文档量大，考虑使用 bge-large 或 OpenAI embeddings 以获得更好的检索效果",
            "切换嵌入模型后需要重新索引所有文档",
        ],
    },
    "retrieval": {
        "title": "检索参数",
        "tips": [
            "top_k 建议设置在 3-8 之间，值越大上下文越丰富但会增加 Token 消耗",
            "score_threshold 建议 0.3-0.5，过低会引入噪声，过高会遗漏相关信息",
            "chunk_size 建议 500-1000，过小丢失上下文，过大降低检索精度",
            "chunk_overlap 建议 chunk_size 的 10-20%，确保跨块信息不丢失",
        ],
    },
    "agent": {
        "title": "Agent 行为配置",
        "tips": [
            "系统提示词（System Prompt）用来设定 AI 的回复风格和行为边界",
            "启用过多的工具会增加 LLM 的决策负担和响应时间",
            "max_tool_rounds 建议 3-5，过多的轮次可能导致 Agent 陷入循环",
            "Web 搜索（SearXNG）需确保 SearXNG 容器正常运行",
        ],
    },
}


MASKED_KEY_PREFIX = "••••••••"

class ConfigUpdate(BaseModel):
    config: dict


def _mask_api_key(key: str) -> str:
    if not key or key.startswith(MASKED_KEY_PREFIX):
        return key
    return "•" * len(key)


@router.get("/config")
async def get_agent_config(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AgentConfig).order_by(AgentConfig.id.desc()).limit(1))
    row = result.scalar_one_or_none()
    overrides = json.loads(row.config_json) if row and row.config_json else {}

    effective = dict(DEFAULT_CONFIG)
    effective.update(overrides)

    has_api_key = bool(effective.get("llm_api_key"))
    effective["llm_api_key"] = _mask_api_key(effective.get("llm_api_key", ""))
    effective["has_api_key"] = has_api_key
    effective["embedding_api_key"] = _mask_api_key(effective.get("embedding_api_key", ""))

    defaults = dict(DEFAULT_CONFIG)
    defaults["llm_api_key"] = _mask_api_key(defaults.get("llm_api_key", ""))
    defaults["has_api_key"] = bool(defaults.get("llm_api_key"))
    defaults["embedding_api_key"] = _mask_api_key(defaults.get("embedding_api_key", ""))

    # Mask keys in overrides too
    masked_overrides = dict(overrides)
    for k in ("llm_api_key", "embedding_api_key"):
        if k in masked_overrides:
            masked_overrides[k] = _mask_api_key(masked_overrides[k])

    return {
        "config": effective,
        "overrides": masked_overrides,
        "defaults": defaults,
    }


@router.put("/config")
async def update_agent_config(
    req: ConfigUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.get("is_super_admin"):
        admin_perms = current_user.get("permissions") or []
        if "agent.config" not in admin_perms:
            raise HTTPException(status_code=403, detail="无权限修改 Agent 配置")

    result = await db.execute(select(AgentConfig).order_by(AgentConfig.id.desc()).limit(1))
    row = result.scalar_one_or_none()

    existing = json.loads(row.config_json) if row and row.config_json else {}

    allowed_keys = set(DEFAULT_CONFIG.keys())
    cleaned = {}
    for k, v in req.config.items():
        if k in allowed_keys:
            # Skip masked keys — user didn't actually provide a new one
            if k in ("llm_api_key", "embedding_api_key") and isinstance(v, str) and (v.startswith(MASKED_KEY_PREFIX) or "•" in v):
                if k in existing:
                    cleaned[k] = existing[k]
                continue
            if isinstance(v, float):
                v = round(v, 2)
            if isinstance(v, str):
                v = v.strip()
            cleaned[k] = v

    existing.update(cleaned)

    if row:
        row.config_json = json.dumps(existing, ensure_ascii=False)
        row.updated_by = current_user.get("user_id", "")
    else:
        db.add(AgentConfig(
            config_json=json.dumps(existing, ensure_ascii=False),
            updated_by=current_user.get("user_id", ""),
        ))
    await db.commit()

    # Invalidate the per-worker config cache so the new values apply immediately.
    try:
        from app.agent.graph import invalidate_effective_config
        invalidate_effective_config()
    except Exception:
        pass

    effective = dict(DEFAULT_CONFIG)
    effective.update(existing)

    has_api_key = bool(effective.get("llm_api_key"))
    effective["llm_api_key"] = _mask_api_key(effective.get("llm_api_key", ""))
    effective["has_api_key"] = has_api_key
    effective["embedding_api_key"] = _mask_api_key(effective.get("embedding_api_key", ""))

    return {"status": "saved", "config": effective}


@router.post("/config/reset")
async def reset_agent_config(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.get("is_super_admin"):
        admin_perms = current_user.get("permissions") or []
        if "agent.config" not in admin_perms:
            raise HTTPException(status_code=403, detail="无权限重置 Agent 配置")

    await db.execute(sql_delete(AgentConfig))
    await db.commit()
    try:
        from app.agent.graph import invalidate_effective_config
        invalidate_effective_config()
    except Exception:
        pass
    reset_cfg = dict(DEFAULT_CONFIG)
    reset_cfg["llm_api_key"] = _mask_api_key(reset_cfg.get("llm_api_key", ""))
    reset_cfg["embedding_api_key"] = _mask_api_key(reset_cfg.get("embedding_api_key", ""))
    return {"status": "reset", "config": reset_cfg}


@router.get("/config/best-practices")
async def get_best_practices(
    current_user: dict = Depends(get_current_user),
):
    return {"sections": BEST_PRACTICES}


class FetchModelsRequest(BaseModel):
    provider: str
    api_key: str
    api_base: str
    type: str = "text"


def _decode_json(resp: httpx.Response) -> dict:
    return json.loads(resp.content.decode("utf-8"))


def _filter_models_by_type(models: list[dict], req_type: str) -> list[dict]:
    """No server-side filtering — return all models; frontend handles display."""
    return models


@router.post("/config/fetch-models")
async def fetch_models(
    req: FetchModelsRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.get("is_super_admin"):
        perms = current_user.get("permissions") or []
        if "agent.config" not in perms:
            raise HTTPException(status_code=403, detail="无权限")

    # Resolve actual API key: if empty or masked, fall back to stored key
    api_key = req.api_key
    if not api_key or "•" in api_key or api_key.startswith(MASKED_KEY_PREFIX):
        result = await db.execute(select(AgentConfig).order_by(AgentConfig.id.desc()).limit(1))
        row = result.scalar_one_or_none()
        if row and row.config_json:
            stored = json.loads(row.config_json)
            api_key = stored.get("llm_api_key", "")
        if not api_key:
            api_key = settings.llm_api_key or ""

    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    provider = req.provider.lower().strip()

    try:
        if provider == "anthropic":
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                )
                resp.raise_for_status()
                data = _decode_json(resp)
                models = [
                    {"id": m["id"], "name": m.get("display_name", m["id"])}
                    for m in data.get("data", [])
                ]
                return {"models": sorted(_filter_models_by_type(models, req.type), key=lambda x: x["id"])}

        elif provider in ("openai", "deepseek", "openrouter", "custom"):
            base = req.api_base.rstrip("/")
            # Use provider-specific endpoint for listing embedding models
            if req.type == "embedding" and provider in ("openai", "openrouter", "custom"):
                embed_url = f"{base}/embeddings/models"
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(embed_url, headers={"Authorization": f"Bearer {api_key}"})
                    if resp.status_code == 404:
                        url = f"{base}/v1/models" if "/v1" not in base else f"{base}/models"
                        resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                    resp.raise_for_status()
                    data = _decode_json(resp)
                    models = [
                        {"id": m["id"], "name": m.get("id", m["id"])}
                        for m in data.get("data", [])
                    ]
                    return {"models": sorted(models, key=lambda x: x["id"])}
            else:
                url = f"{base}/v1/models" if "/v1" not in base else f"{base}/models"
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                    resp.raise_for_status()
                    data = _decode_json(resp)
                    models = [
                        {"id": m["id"], "name": m.get("id", m["id"])}
                        for m in data.get("data", [])
                    ]
                    return {"models": sorted(models, key=lambda x: x["id"])}

        elif provider == "ollama":
            base = req.api_base.rstrip("/")
            url = f"{base}/api/tags"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = _decode_json(resp)
                models = [
                    {"id": m["name"], "name": m["name"]}
                    for m in data.get("models", [])
                ]
                return {"models": sorted(_filter_models_by_type(models, req.type), key=lambda x: x["id"])}

        else:
            raise HTTPException(status_code=400, detail=f"不支持的提供商: {provider}")

    except httpx.HTTPStatusError as e:
        logger.warning("fetch models HTTP %s for %s: %.200s", e.response.status_code, provider, e.response.text)
        raise HTTPException(status_code=502, detail=f"API 请求失败 ({e.response.status_code})")
    except HTTPException:
        # Already a proper client error (400/403/...); don't mask it as 500.
        raise
    except httpx.RequestError:
        logger.warning("fetch models connection failed: %s", provider)
        raise HTTPException(status_code=502, detail="无法连接到 API 服务")
    except UnicodeEncodeError:
        raise HTTPException(status_code=502, detail="API 返回编码异常")
    except Exception as e:
        logger.warning("fetch models error: %s", e)
        raise HTTPException(status_code=500, detail="获取模型列表失败，请稍后重试")


# ── Embedding local model: prepare (download with progress) + apply (rebuild) ──

@router.get("/config/embedding/status")
async def embedding_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Readiness of the *effective* embedding for knowledge retrieval.

    Returns {provider, model, ready, reason} where reason explains why the
    configured embedding cannot serve retrieval right now:
      - model_not_downloaded: local model selected but not in the local cache
      - unsupported_model:    local model name is not in fastembed's list
      - empty_model:          local mode selected but no model name configured
      - no_api_key:           remote embedding without any usable API key
    """
    from app.vector.model_downloader import resolve_local_model, is_local_model_ready

    try:
        from app.agent.runtime_config import get_effective_config
        cfg = await get_effective_config()
    except Exception:
        cfg = {}
    cfg = cfg or {}
    provider = cfg.get("embedding_provider") or "local"
    model = (cfg.get("embedding_model") or "").strip()
    out = {"provider": provider, "model": model, "ready": True, "reason": "", "local_supported": None}

    if provider == "local":
        if not model:
            out.update({"ready": False, "reason": "empty_model", "local_supported": False})
            return out
        try:
            spec = resolve_local_model(model)
            out["local_supported"] = True
            out["hf_repo"] = spec["hf_repo"]
        except ValueError:
            out.update({"ready": False, "reason": "unsupported_model", "local_supported": False})
            return out
        if not is_local_model_ready(model):
            out.update({"ready": False, "reason": "model_not_downloaded"})
            return out
        return out

    # Remote embeddings need a usable API key (embedding key -> LLM key fallback).
    has_key = bool(cfg.get("embedding_api_key") or settings.embedding_api_key
                   or cfg.get("llm_api_key") or settings.llm_api_key)
    if not has_key:
        out.update({"ready": False, "reason": "no_api_key"})
    return out


@router.get("/config/embedding/models")
async def embedding_models(current_user: dict = Depends(get_current_user)):
    """List local (fastembed) supported embedding models with dim/size/cached."""
    _require_agent_perm(current_user)
    from app.vector.model_downloader import list_local_candidates, is_local_model_ready
    items = []
    for m in list_local_candidates():
        try:
            mid = str(m.get("model") or "")
            if not mid:
                continue
            if not (m.get("sources") or {}).get("hf") and not (m.get("model_file")):
                continue
        except Exception:
            continue
        items.append({
            "id": "local/" + mid,
            "name": mid,
            "dim": int(m.get("dim") or 0),
            "size_gb": float(m.get("size_in_GB") or 0.0),
            "description": (m.get("description") or "")[:120],
            "cached": is_local_model_ready("local/" + mid),
        })
    items.sort(key=lambda x: (x["name"].lower(),))
    return {"models": items, "total": len(items)}

class EmbeddingPrepareRequest(BaseModel):
    model: str = ""
    provider: str = ""


def _sses(obj: dict) -> str:
    """Encode one SSE event line."""
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _require_agent_perm(current_user: dict):
    if not current_user.get("is_super_admin"):
        perms = current_user.get("permissions") or []
        if "agent.config" not in perms:
            raise HTTPException(status_code=403, detail="无权限")


@router.post("/config/embedding/delete")
async def embedding_delete(
    req: EmbeddingPrepareRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a downloaded local embedding model from the cache.

    Only removes the model's own cache folder; other models and the vector
    index are untouched (the model can be re-downloaded via prepare later).
    """
    _require_agent_perm(current_user)
    from app.vector.model_downloader import remove_local_model, is_local_model_ready
    model = (req.model or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="模型名为空")
    result = remove_local_model(model)
    return {"status": "ok", "removed": result.get("removed", False), "repo": result.get("repo"), "still_ready": is_local_model_ready(model)}


@router.post("/config/embedding/prepare")
async def embedding_prepare(
    req: EmbeddingPrepareRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream progress while ensuring the local embedding model is available.

    Emits SSE events: {stage}, {progress}, then {status: ready|error}.
    The configured download provider is used; on failure the official Hub is
    retried automatically.
    """
    _require_agent_perm(current_user)

    from app.vector.model_downloader import resolve_local_model, is_local_model_ready, download_model

    model = (req.model or "").strip()
    if not model or not model.lower().startswith("local/"):
        return StreamingResponse(_sse_events([{"status": "error", "detail": "仅支持本地模型（local/ 前缀）"}]), media_type="text/event-stream")

    # Provider: request value -> stored override -> env default
    provider = (req.provider or "").strip() or ""
    if not provider:
        try:
            result = await db.execute(select(AgentConfig).order_by(AgentConfig.id.desc()).limit(1))
            row = result.scalar_one_or_none()
            if row and row.config_json:
                provider = (json.loads(row.config_json) or {}).get("embedding_download_provider", "")
        except Exception:
            provider = ""
    provider = provider or settings.embedding_download_provider

    q: "queue.Queue" = queue.Queue()

    def _run():
        try:
            spec = resolve_local_model(model)
        except ValueError as e:
            q.put(("error", str(e)))
            return
        if is_local_model_ready(model):
            q.put(("ready", {"model": model, "cached": True, "repo": spec["hf_repo"]}))
            return

        def _on_progress(p, msg):
            q.put(("progress", {"progress": round(p, 4) if p is not None else None, "message": msg}))

        def _on_stage(stage):
            q.put(("stage", stage))

        try:
            r = download_model(spec, provider, _on_progress, _on_stage)
            q.put(("ready", {"model": model, "cached": bool(r.get("cached")), "repo": r.get("repo"), "provider": r.get("provider")}))
        except Exception as e:  # noqa: BLE001
            q.put(("error", str(e)))

    thread = threading.Thread(target=_run, daemon=True)

    async def _gen():
        thread.start()
        last_sent: float = -1.0
        while thread.is_alive() or not q.empty():
            # Non-blocking for the event loop: a blocking q.get here would stall
            # ALL coroutines on this worker for 0.5s per empty iteration, which
            # delayed SSE delivery (progress appeared only at the very end).
            try:
                kind, payload = await asyncio.wait_for(asyncio.to_thread(q.get), timeout=1.5)
            except (asyncio.TimeoutError, TimeoutError):
                if not thread.is_alive() and q.empty():
                    break
                continue
            if kind == "error":
                yield _sses({"status": "error", "detail": payload})
                return
            if kind == "stage":
                yield _sses({"stage": payload})
            elif kind == "progress":
                p = payload.get("progress")
                # Light throttle: emit every meaningful jump ≥0.5% so the UI bar
                # moves smoothly without flickering at byte granularity.
                if isinstance(p, (int, float)) and isinstance(last_sent, (int, float)) and p - last_sent < 0.005:
                    continue
                last_sent = p
                yield _sses({"stage": "downloading", "progress": p, "message": payload.get("message", "正在下载本地嵌入模型")})
            elif kind == "ready":
                yield _sses({"status": "ready", **payload})
                return
        yield _sses({"status": "error", "detail": "下载中断"})

    return StreamingResponse(_gen(), media_type="text/event-stream")


def _drop_vector_collection() -> None:
    from pymilvus import MilvusClient
    client = MilvusClient(uri=settings.milvus_uri)
    try:
        if client.has_collection(settings.milvus_collection):
            client.drop_collection(settings.milvus_collection)
    finally:
        client.close()


@router.post("/config/embedding/apply")
async def embedding_apply(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rebuild the vector store & reindex all documents with the NEW embedding.

    Runs only after the embedding config has been saved. Verifies the new
    embedding works before dropping the old collection so a failed model never
    leaves the system without data.
    """
    _require_agent_perm(current_user)

    async def _gen():
        # 1) Build the new embeddings from effective config and verify they work.
        from app.vector.embeddings import get_embeddings_async
        try:
            emb = await get_embeddings_async()
            probe = await asyncio.to_thread(emb.embed_query, "维度探测 probe test 测试")
            dim = len(probe)
            yield _sses({"stage": "verify", "message": f"新嵌入模型可用（维度 {dim}）"})
        except Exception as e:  # noqa: BLE001
            yield _sses({"status": "error", "detail": f"嵌入模型不可用: {str(e)[:160]}"})
            return

        # 2) Drop old collection (different dim) then rebuild the wrapper.
        try:
            await asyncio.to_thread(_drop_vector_collection)
            yield _sses({"stage": "rebuild", "message": "底层向量库已重建，正在重新索引文档…"})
        except Exception as e:  # noqa: BLE001
            yield _sses({"status": "error", "detail": f"重建向量库失败: {str(e)[:160]}"})
            return

        from app.vector.store import rebuild_vector_store, get_vector_store
        from app.documents.registry import list_document_entries
        from langchain_core.documents import Document
        try:
            rebuild_vector_store()
            store = get_vector_store()
        except Exception as e:  # noqa: BLE001
            yield _sses({"status": "error", "detail": f"初始化向量库失败: {str(e)[:160]}"})
            return

        entries = list_document_entries() or []
        total = sum(len(e.get("chunks") or []) for e in entries)
        done = 0
        try:
            for e in entries:
                chunks = e.get("chunks") or []
                if not chunks:
                    continue
                # Replicate the exact metadata shape used by the document uploader
                # (source/doc_id/chunk_index/file_hash/uploaded_at) so the rebuilt
                # Milvus schema/query fields match and retrieval keeps working.
                import hashlib
                joined = " ".join((c.get("content") or "") for c in chunks)
                file_hash = hashlib.md5(joined.encode("utf-8")).hexdigest()
                uploaded_at = e.get("uploaded_at") or __import__("datetime").datetime.now().isoformat()
                docs = [
                    Document(
                        page_content=(c.get("content") or ""),
                        metadata={
                            "source": (e.get("filename") or ""),
                            "doc_id": (e.get("id") or ""),
                            "chunk_index": int(c.get("index", 0) or 0),
                            "file_hash": file_hash,
                            "uploaded_at": uploaded_at,
                        },
                    )
                    for c in chunks
                ]
                await asyncio.to_thread(store.add_documents, docs)
                done += len(docs)
                yield _sses({
                    "stage": "indexing",
                    "done": done,
                    "total": total,
                    "progress": round(done / total, 4) if total else 1.0,
                })
        except Exception as e:  # noqa: BLE001
            try:
                yield _sses({"status": "error", "detail": f"文档索引失败: {str(e)[:160]}"})
            except Exception:
                pass
            return
        try:
            yield _sses({"status": "ok", "indexed": done, "dim": dim, "total": total})
        except Exception:
            pass

    return StreamingResponse(_gen(), media_type="text/event-stream")
