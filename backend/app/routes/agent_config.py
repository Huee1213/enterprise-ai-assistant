import json
import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends
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
    except httpx.RequestError:
        logger.warning("fetch models connection failed: %s", provider)
        raise HTTPException(status_code=502, detail="无法连接到 API 服务")
    except UnicodeEncodeError:
        raise HTTPException(status_code=502, detail="API 返回编码异常")
    except Exception as e:
        logger.warning("fetch models error: %s", e)
        raise HTTPException(status_code=500, detail="获取模型列表失败，请稍后重试")
