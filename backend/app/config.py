from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "Enterprise AI Knowledge Assistant"
    debug: bool = False

    # LLM Configuration via LiteLLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: Optional[str] = None
    llm_api_base: Optional[str] = None
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096

    # Embedding
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: Optional[str] = None
    embedding_api_base: Optional[str] = None
    # Provider used to download local embedding models (HF-compatible mirror).
    embedding_download_provider: str = "https://hf-mirror.com"

    # Milvus
    milvus_uri: str = "http://milvus:19530"
    milvus_collection: str = "enterprise_knowledge"
    milvus_dimension: int = 384

    # Storage
    upload_dir: str = "/app/data/documents"
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Retrieval
    top_k: int = 5
    score_threshold: float = 0.5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
