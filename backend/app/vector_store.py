from typing import List, Optional
from langchain_milvus import Milvus
from langchain_core.documents import Document
from app.config import settings
from app.embeddings import get_embeddings


_vector_store: Optional[Milvus] = None


def get_vector_store() -> Milvus:
    global _vector_store
    if _vector_store is None:
        embeddings = get_embeddings()
        _vector_store = Milvus(
            embedding_function=embeddings,
            collection_name=settings.milvus_collection,
            connection_args={
                "uri": settings.milvus_uri,
            },
            auto_id=True,
            drop_old=False,
        )
    return _vector_store


def add_documents(documents: List[Document]) -> List[str]:
    store = get_vector_store()
    return store.add_documents(documents)


def similarity_search(query: str, k: int = 5) -> List[Document]:
    store = get_vector_store()
    return store.similarity_search(query, k=k)


def hybrid_search(query: str, k: int = 5) -> List[Document]:
    store = get_vector_store()
    return store.similarity_search(query, k=k)


def delete_document(doc_id: str) -> None:
    store = get_vector_store()
    store.delete(ids=[doc_id])


def get_collection_stats() -> dict:
    try:
        from pymilvus import Collection, connections

        connections.connect(
            alias="default",
            uri=settings.milvus_uri,
        )
        collection = Collection(settings.milvus_collection)
        collection.load()
        stats = {
            "row_count": collection.num_entities,
            "collection_name": settings.milvus_collection,
        }
        return stats
    except Exception as e:
        return {"error": str(e)}
