from pymilvus import MilvusClient
c = MilvusClient(uri="http://milvus:19530")
r = c.query(collection_name="enterprise_knowledge", filter="", output_fields=["pk", "doc_id", "source"], limit=100)
print(f"Total: {len(r)}")
for x in r:
    print(f"  pk={x['pk']} doc_id={x.get('doc_id','?')[:20]} source={x.get('source','?')}")
c.close()
