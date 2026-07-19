"""Verify if delete_document actually works by directly testing."""
import sys, asyncio, json

async def main():
    doc_id = sys.argv[1] if len(sys.argv) > 1 else ""

    from pymilvus import MilvusClient
    client = MilvusClient(uri="http://milvus:19530")

    # Check if collection exists
    cols = client.list_collections()
    if "enterprise_knowledge" not in cols:
        print("Collection not found")
        return

    # Query for the doc_id
    results = client.query(
        collection_name="enterprise_knowledge",
        filter=f'doc_id == "{doc_id}"',
        output_fields=["pk"],
        limit=100,
    )
    print(f"Found {len(results)} entries for doc_id={doc_id}")

    if results:
        print(f"PKs to delete: {[r['pk'] for r in results]}")
        result = client.delete(
            collection_name="enterprise_knowledge",
            ids=[r["pk"] for r in results],
        )
        print(f"Delete result: {result}")
        client.flush(collection_name="enterprise_knowledge")

        # Verify deletion
        verify = client.query(
            collection_name="enterprise_knowledge",
            filter=f'doc_id == "{doc_id}"',
            output_fields=["pk"],
            limit=100,
        )
        print(f"After delete: {len(verify)} entries remaining")
    else:
        print("No entries to delete")

    # Show first 5 entries
    sample = client.query(
        collection_name="enterprise_knowledge",
        filter="",
        output_fields=["pk", "doc_id", "source"],
        limit=5,
    )
    print("\nFirst 5 entries:")
    for r in sample:
        print(f"  pk={r['pk']} doc_id={str(r.get('doc_id',''))[:20]} source={str(r.get('source',''))[:30]}")

    client.close()

if __name__ == "__main__":
    asyncio.run(main())
