import logging
from typing import List, Optional, Callable
from langchain_milvus import Milvus
from langchain_core.documents import Document
from app.config import settings
from app.vector.embeddings import get_embeddings

logger = logging.getLogger("vector_store")

_vector_store: Optional[Milvus] = None


def get_vector_store(reuse: bool = True) -> Milvus:
    """Return the cached vector store, optionally rebuilding it.

    `reuse=False` forces a fresh Milvus wrapper with the current embedding
    config, so switching embedding model/key on the config page takes effect
    without a process restart.
    """
    global _vector_store
    if reuse and _vector_store is not None:
        return _vector_store
    embeddings = get_embeddings()
    store = Milvus(
        embedding_function=embeddings,
        collection_name=settings.milvus_collection,
        connection_args={"uri": settings.milvus_uri},
        auto_id=True,
        drop_old=False,
    )
    if reuse:
        _vector_store = store
    return store


def rebuild_vector_store() -> Milvus:
    """Force-rebuild the vector store with the current config and return it."""
    return get_vector_store(reuse=False)


# Last applied similarity threshold (so embed changes aren't lost on rebuild).
_sim_threshold: float = 0.0


def _apply_threshold(docs: List[Document], threshold: float) -> List[Document]:
    if not threshold or threshold <= 0:
        return docs
    kept = []
    for d in docs:
        try:
            score = float(d.metadata.get("score") or d.metadata.get("relevance_score") or 0.0)
        except Exception:
            score = 0.0
        if score >= threshold:
            kept.append(d)
    return kept


def add_documents(documents: List[Document]) -> List[str]:
    return get_vector_store().add_documents(documents)


def similarity_search(query: str, k: int = 5, threshold: float = 0.0) -> List[Document]:
    docs = get_vector_store().similarity_search_with_score(query, k=max(1, k))
    # Milvus similarity_search_with_score returns (Document, score) pairs.
    if docs and isinstance(docs[0], tuple):
        filtered = []
        for doc, score in docs:
            if threshold and threshold > 0 and float(score) < threshold:
                continue
            matched = Document(
                page_content=doc.page_content,
                metadata={**doc.metadata, "score": float(score)},
            )
            filtered.append(matched)
        return filtered
    # Fallback: plain list (no scores) — return as-is.
    return docs


def _new_client():
    """Create a dedicated MilvusClient per call to avoid gRPC contention."""
    from pymilvus import MilvusClient
    return MilvusClient(uri=settings.milvus_uri)


def _collect_pks(client, coll_name: str, doc_ids: List[str]) -> list:
    """Query and return all PKs matching the given doc_ids."""
    all_pks: list = []
    for doc_id in doc_ids:
        results = client.query(
            collection_name=coll_name,
            filter=f'doc_id == "{doc_id}"',
            output_fields=["pk"],
            limit=10000,
        )
        all_pks.extend(r["pk"] for r in results)
    return all_pks


def delete_document(doc_id: str) -> None:
    """Delete vectors matching one doc_id. Uses a dedicated MilvusClient."""
    try:
        client = _new_client()
        try:
            coll_name = settings.milvus_collection
            client.load_collection(coll_name)
            pks = _collect_pks(client, coll_name, [doc_id])
            if pks:
                client.delete(collection_name=coll_name, ids=pks)
                logger.info(f"deleted {len(pks)} vectors for doc_id={doc_id}")
            else:
                logger.warning(f"No vectors found for doc_id={doc_id}")
        finally:
            client.close()
    except Exception as e:
        logger.error(f"delete_document error: {e}")


def batch_delete_documents(doc_ids: List[str]) -> None:
    """Delete vectors matching multiple doc_ids in one batch operation."""
    try:
        client = _new_client()
        try:
            coll_name = settings.milvus_collection
            client.load_collection(coll_name)
            pks = _collect_pks(client, coll_name, doc_ids)
            if pks:
                r = client.delete(collection_name=coll_name, ids=pks)
                client.flush(collection_name=coll_name)
                logger.info(f"deleted {r.get('delete_count',0)} vectors for {len(doc_ids)} doc(s) (pk_count={len(pks)})")
            else:
                logger.warning(f"No vectors found for doc_ids={doc_ids}")
        finally:
            client.close()
    except Exception as e:
        logger.error(f"batch_delete_documents error: {e}")


def get_collection_stats() -> dict:
    try:
        from pymilvus import MilvusClient
        client = MilvusClient(uri=settings.milvus_uri)
        stats = client.query_collection_stats(settings.milvus_collection)
        client.close()
        return {"row_count": stats.get("row_count", 0), "collection_name": settings.milvus_collection}
    except Exception as e:
        return {"error": str(e)}
