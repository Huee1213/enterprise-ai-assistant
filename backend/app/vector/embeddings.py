from app.config import settings
from app.agent.runtime_config import get_effective_config
from langchain_core.embeddings import Embeddings


def _build_embeddings(cfg: dict) -> Embeddings:
    model = (cfg.get("embedding_model") or settings.embedding_model or "").strip()
    use_local = model.startswith("local/")
    if use_local:
        from langchain_community.embeddings import FastEmbedEmbeddings
        model_name = model.replace("local/", "", 1)
        # Explicit cache dir: Docker Desktop can pollute HOME (e.g. "C:UsersX"),
        # which would break the default ~/.cache/fastembed lookup and force a
        # (failing) runtime re-download. The model is baked into the image here.
        return FastEmbedEmbeddings(model_name=model_name, cache_dir="/root/.cache/fastembed")

    from langchain_openai import OpenAIEmbeddings
    api_key = (cfg.get("embedding_api_key") or settings.embedding_api_key
               or cfg.get("llm_api_key") or settings.llm_api_key)
    base_url = (cfg.get("embedding_api_base") or settings.embedding_api_base
                or cfg.get("llm_api_base") or settings.llm_api_base)
    kwargs = {"model": model, "api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAIEmbeddings(**kwargs)


async def get_embeddings_async() -> Embeddings:
    """Load embeddings honouring the agent config DB overrides."""
    cfg = await get_effective_config()
    return _build_embeddings(cfg)


def get_embeddings() -> Embeddings:
    """Sync loader for thread/executor contexts (document indexing & retrieval).

    Loads DB overrides so embedding model / key / base saved on the agent config
    page actually take effect. Worker threads have no running loop, so a fresh
    event loop is used; async callers should use get_embeddings_async().
    """
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            cfg = loop.run_until_complete(get_effective_config())
        finally:
            loop.close()
        return _build_embeddings(cfg)
    # Running loop: cannot block. Fall back to env defaults for sync callers.
    return _build_embeddings({})
