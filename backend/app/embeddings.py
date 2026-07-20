from app.config import settings
from langchain_core.embeddings import Embeddings


def _ensure_embeddings_base(base: str) -> str:
    """Ensure the base URL points to the embeddings endpoint.
    
    For OpenAI-compatible APIs, the embeddings endpoint is at {base}/embeddings.
    The OpenAI client appends /embeddings automatically — we keep the base clean.
    """
    base = base.rstrip("/")
    # If the base already contains '/embeddings', use as-is
    if "/embeddings" in base:
        return base
    return base


def get_embeddings() -> Embeddings:
    use_local = settings.embedding_model.startswith("local/")
    if use_local:
        from langchain_community.embeddings import FastEmbedEmbeddings
        model_name = settings.embedding_model.replace("local/", "", 1)
        return FastEmbedEmbeddings(model_name=model_name)
    else:
        from langchain_openai import OpenAIEmbeddings
        api_key = settings.embedding_api_key or settings.llm_api_key
        kwargs = {
            "model": settings.embedding_model,
            "api_key": api_key,
        }
        base_url = settings.embedding_api_base or settings.llm_api_base
        if base_url:
            kwargs["base_url"] = _ensure_embeddings_base(base_url)
        return OpenAIEmbeddings(**kwargs)
