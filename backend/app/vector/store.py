import logging
import threading
from typing import List, Optional, Callable
from langchain_milvus import Milvus
from langchain_core.documents import Document
from app.config import settings
from app.vector.embeddings import get_embeddings

logger = logging.getLogger("vector_store")

_vector_store: Optional[Milvus] = None
_schema_lock = threading.Lock()
_schema_checked = False


def _fresh_store(embeddings) -> Milvus:
    return Milvus(
        embedding_function=embeddings,
        collection_name=settings.milvus_collection,
        connection_args={"uri": settings.milvus_uri},
        auto_id=True,
        drop_old=False,
    )


def _collection_vector_dim() -> Optional[int]:
    """Read the vector-field dimension of the existing collection, or None."""
    try:
        from pymilvus import MilvusClient
        client = MilvusClient(uri=settings.milvus_uri)
        try:
            if not client.has_collection(settings.milvus_collection):
                return None
            desc = client.describe_collection(settings.milvus_collection)
            for f in desc.get("fields", []):
                if f.get("name") == "vector" or f.get("type") in (101, 102):  # FLOAT_VECTOR/BINARY
                    p = f.get("params") or {}
                    dim = p.get("dim")
                    return int(dim) if dim else None
            return None
        finally:
            client.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("read collection dim failed: %s", e)
        return None


def _drop_collection() -> None:
    from pymilvus import MilvusClient
    client = MilvusClient(uri=settings.milvus_uri)
    try:
        if client.has_collection(settings.milvus_collection):
            client.drop_collection(settings.milvus_collection)
            logger.info("dropped collection %s", settings.milvus_collection)
    finally:
        client.close()


def reindex_all_from_registry(store: Milvus) -> int:
    """Re-index every registered document chunk into `store`.

    Keeps metadata identical to the original uploader
    (source/doc_id/chunk_index/file_hash/uploaded_at).
    """
    from app.documents.registry import list_document_entries
    import hashlib
    import datetime as _dt
    entries = list_document_entries() or []
    total = done = 0
    for e in entries:
        chunks = e.get("chunks") or []
        if not chunks:
            continue
        total += len(chunks)
        joined = " ".join((c.get("content") or "") for c in chunks)
        file_hash = hashlib.md5(joined.encode("utf-8")).hexdigest()
        uploaded_at = e.get("uploaded_at") or _dt.datetime.now().isoformat()
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
        store.add_documents(docs)
        done += len(docs)
    logger.info("reindexed %s/%s chunks", done, total)
    return done


def get_vector_store(reuse: bool = True) -> Milvus:
    """Return the cached vector store, optionally rebuilding it.

    `reuse=False` forces a fresh Milvus wrapper with the current embedding
    config. When the embedding model changes (dimension mismatch with the
    existing collection), the store is automatically dropped and all documents
    are re-indexed so knowledge retrieval keeps working without a manual step.
    """
    global _vector_store, _schema_checked
    if reuse and _vector_store is not None:
        return _vector_store

    # Validate/align the schema once per process (fresh wrapper path).
    with _schema_lock:
        embeddings = get_embeddings()
        store = _fresh_store(embeddings)
        if reuse:
            try:
                if not _schema_checked:
                    try:
                        probe_dim = len(embeddings.embed_query("__dim_probe__"))
                    except Exception as e:  # noqa: BLE001
                        probe_dim = 0
                        logger.warning("embed probe failed: %s", e)
                    coll_dim = _collection_vector_dim()
                    if coll_dim and probe_dim and coll_dim != probe_dim:
                        logger.warning(
                            "embedding dimension mismatch (query=%s, collection=%s) — re-indexing",
                            probe_dim, coll_dim,
                        )
                        _drop_collection()
                        fresh = _fresh_store(embeddings)
                        try:
                            reindex_all_from_registry(fresh)
                        except Exception as e:  # noqa: BLE001
                            logger.error("auto re-index failed: %s", e)
                        store = _fresh_store(embeddings)
                    _schema_checked = True
            except Exception as e:  # noqa: BLE001
                logger.error("schema alignment failed: %s", e)
            _vector_store = store
    return store


def rebuild_vector_store() -> Milvus:
    """Force-rebuild the vector store with the current config and return it."""
    return get_vector_store(reuse=False)


def _guarded(fn, *args, **kwargs):
    """Run an operation, and retry once against a freshly rebuilt vector store.

    When the embedding model changes, the Milvus collection is dropped and
    recreated with a new schema (dimension). Other gunicorn workers may still
    hold a stale wrapper; retrying after rebuilding makes them self-heal.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        try:
            rebuild_vector_store()
        except Exception:
            raise e
        return fn(*args, **kwargs)


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
    def _op():
        return get_vector_store().add_documents(documents)
    return _guarded(_op)


def similarity_search(query: str, k: int = 5, threshold: float = 0.0) -> List[Document]:
    def _op():
        return get_vector_store().similarity_search_with_score(query, k=max(1, k))
    docs = _guarded(_op)
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
