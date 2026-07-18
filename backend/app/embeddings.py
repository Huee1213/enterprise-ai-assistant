from app.config import settings
from langchain_core.embeddings import Embeddings


def get_embeddings() -> Embeddings:
    use_local = settings.embedding_model.startswith("local/")
    if use_local:
        from langchain_community.embeddings import FastEmbedEmbeddings
        model_name = settings.embedding_model.replace("local/", "", 1)
        return FastEmbedEmbeddings(model_name=model_name)
    else:
        from langchain_openai import OpenAIEmbeddings
        kwargs = {
            "model": settings.embedding_model,
            "api_key": settings.embedding_api_key or settings.llm_api_key,
        }
        base_url = settings.embedding_api_base or settings.llm_api_base
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAIEmbeddings(**kwargs)
