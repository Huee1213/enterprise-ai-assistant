from app.config import settings
from app.runtime_config import get_effective_config
from langchain_core.embeddings import Embeddings


def get_embeddings() -> Embeddings:
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        cfg = loop.run_until_complete(get_effective_config())
    except Exception:
        cfg = {}

    model = cfg.get("embedding_model", settings.embedding_model) or settings.embedding_model
    use_local = model.startswith("local/")
    if use_local:
        from langchain_community.embeddings import FastEmbedEmbeddings
        model_name = model.replace("local/", "", 1)
        return FastEmbedEmbeddings(model_name=model_name)
    else:
        from langchain_openai import OpenAIEmbeddings
        api_key = cfg.get("embedding_api_key", "") or settings.embedding_api_key or cfg.get("llm_api_key", "") or settings.llm_api_key
        base_url = cfg.get("embedding_api_base", "") or settings.embedding_api_base or cfg.get("llm_api_base", "") or settings.llm_api_base
        kwargs = {"model": model, "api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAIEmbeddings(**kwargs)
