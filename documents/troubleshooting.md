# 排错与调试指南

> 记录开发与部署过程中遇到的常见问题、根因分析及解决方案。

---

## 目录

1. [Milvus 删除后仍能检索到文档](#1-milvus-删除后仍能检索到文档)
2. [连续删除文档第二个请求明显变慢](#2-连续删除文档第二个请求明显变慢)
3. [`/api/documents/list` 重复调用](#3-apidocumentslist-重复调用)
4. [Vite 构建缓存导致 ReferenceError](#4-vite-构建缓存导致-referenceerror)
5. [Docker `COPY . .` 层缓存导致旧数据残留](#5-docker-copy--层缓存导致旧数据残留)
6. [LangGraph 状态机流式输出异常](#6-langgraph-状态机流式输出异常)
7. [PostgreSQL 连接池耗尽](#7-postgresql-连接池耗尽)
8. [前端 SSE 流式中断问题](#8-前端-sse-流式中断问题)
9. [高并发下 MilvusClient gRPC 连接争抢](#9-高并发下-milvusclient-grpc-连接争抢)
10. [后台页面文档详情弹窗关闭交互问题](#10-后台页面文档详情弹窗关闭交互问题)

---

## 1. Milvus 删除后仍能检索到文档

### 现象

通过「文档管理」删除文档后，Agent/搜索仍然返回已删除文档的内容。

### 根因分析

**问题 1：`doc_id` 不匹配**

`document_processor.process_file()` 内部生成独立的 `uuid4()` 作为 metadata 的 `doc_id`，与路由层生成的 `doc_id` 不一致。

```
路由: doc_id = str(uuid.uuid4())            → "a1b2c3d4-..."
处理器: doc_id = str(uuid.uuid4())          → "e5f6g7h8-..."  ← 不同！
Milvus 向量 metadata.doc_id = "e5f6g7h8-..."
注册表 doc_id  = "a1b2c3d4-..."
delete_document("a1b2c3d4-...") → 按 doc_id 查 Milvus → 找不到 → 删除静默失败
```

**问题 2：`_reindex_registry` 未传递 `doc_id`**

启动时 `_reindex_registry` 调用 `processor.process_file(path, name)` 未传递 `doc_id`，重新索引的向量携带了不同的 `doc_id`，导致这些向量永远无法通过注册表中的 `doc_id` 删除。

**问题 3：MilvusClient vs ORM Collection 连接不一致**

`delete_document` 使用 `pymilvus.MilvusClient`（HTTP/gRPC 独立连接），而 `similarity_search` 通过 `langchain_milvus.Milvus` 内部维护的 `_milvus_client` 查询。两者使用不同的 gRPC 连接上下文，导致删除操作对搜索不可见。

### 解决方案

1.  `processor.process_file()` 接受可选 `doc_id` 参数，路由传入 `doc_id=doc_id` 保持一致
2.  `_reindex_registry` 调用时传入注册表中的 `doc_id`
3.  `delete_document` 使用 `store._milvus_client`（即 langchain_milvus 内部 client）执行删除，确保与搜索同连接

### 涉及文件

- `backend/app/document_processor.py` — `process_file()` 增加 `doc_id` 参数
- `backend/app/vector_store.py` — `delete_document()` / `batch_delete_documents()` 使用 `store._milvus_client`
- `backend/app/main.py` — `_reindex_registry()` 传递 `doc_id`
- `backend/app/routes/documents.py` — 所有上传路径传递 `doc_id`

---

## 2. 连续删除文档第二个请求明显变慢

### 现象

连续删除两个文档：第一个 ~0.35s，第二个 ~11s（慢 30 倍）。

### 根因分析

`delete_document` 执行完毕后设置 `_vector_store = None`，第二个删除调用 `get_vector_store()` 时需创建全新的 `langchain_milvus.Milvus` 实例。该构造函数内创建 `MilvusClient` 和 `AsyncMilvusClient`，涉及网络连接和元数据加载，耗时 ~10s。

### 解决方案

- 移除成功路径上的 `_vector_store = None`，单例保持存活
- `delete_document` 不再调用 `flush()`（~2-3s），仅做 `delete` 操作
- `batch_delete_documents` 保留单次 `flush()` 保证数据持久性

### 涉及文件

- `backend/app/vector_store.py` — `delete_document()` 去 `flush` / `_vector_store = None`

### 性能对比

| 操作 | 优化前 | 优化后 |
|------|--------|--------|
| 第 1 个删除 | ~4.9s | ~0.36s |
| 第 2 个删除 | ~11.4s | ~0.35s |
| 第 3 个删除 | — | ~0.35s |

---

## 3. `/api/documents/list` 重复调用

### 现象

上传文档后触发两次 `/api/documents/list` 请求。

### 根因分析

`DocumentsView.onUploaded()` 同时调用 `fetchDocuments()` 和 `refreshStats()`，两者各自调用了一次 `/api/documents/list`。

### 解决方案

- `onUploaded()` 只调用 `refreshStats()`
- `refreshStats()` 内部通过 `setDocuments(data)` 更新列表，不再额外请求
- 删除「全选」也在 `setDocuments` 时清除选择状态

### 涉及文件

- `frontend/src/views/DocumentsView.vue` — `onUploaded` 逻辑
- `frontend/src/components/documents/DocumentList.vue` — `setDocuments` 方法

---

## 4. Vite 构建缓存导致 ReferenceError

### 现象

修改前端代码后重新构建，运行时出现 `XXX is not defined` 或 `watch not defined` 等 ReferenceError。

### 根因分析

Vite 的依赖预构建缓存 (`node_modules/.vite`) 在依赖版本或导入路径变更后未自动失效，导致打包输出包含过时的模块引用。

### 解决方案

```bash
# 清理 vite 缓存并重建
rm -rf node_modules/.vite
npm run build

# 或使用 docker 时强制无缓存构建
docker compose build --no-cache frontend
docker compose up -d frontend
```

---

## 5. Docker `COPY . .` 层缓存导致旧数据残留

### 现象

`docker compose down -v` 清空所有卷后启动，数据目录仍出现旧的种子文档文件。

### 根因分析

Docker 构建 `COPY . .` 层被 CACHED。当宿主机的 `backend/` 目录没有 `data/documents/` 时，但缓存层来自之前某次构建（该次构建时目录下有文件），新构建复用缓存导致旧文件被「冻结」在镜像中。

当新卷创建时，Docker 将镜像中 `/app/data/` 的内容（含旧种子文件）初始化到卷中，导致 `reindex` 使用旧数据。

### 解决方案

```bash
# 强制无缓存构建（不信任 COPY 缓存）
docker compose build --no-cache backend
docker compose down -v
docker compose up -d
```

### 预防

- 不在构建时将数据文件 `COPY` 到镜像内
- 使用独立的初始化脚本或卷挂载

---

## 6. LangGraph 状态机流式输出异常

### 现象

Agent 模式下的流式 SSE 输出中断、重复或缺失工具调用结果。

### 根因分析

**常见原因：**

1.  `stream_mode` 设置不正确。LangGraph v1 需要 `stream_mode="updates"` 才能捕获所有节点（包括 ToolNode）的输出。
2.  `ToolNode` 返回格式错误。Tool 的输出必须是 `{"messages": [result]}` 格式。
3.  `conditional_edges` 路径映射未使用显式字典。LangGraph v1 不自动匹配字符串到 `END`，需使用 `{"continue": "tools", "end": END}` 形式。
4.  `ModelRequestError` 后节点重试逻辑缺失，异常被吞掉。

### 解决方案

```python
graph = workflow.compile(interrupt_before=[], interrupt_after=[])
# 使用 stream_mode="updates" 捕获所有节点
for event in graph.astream(input, config, stream_mode="updates"):
    for node, output in event.items():
        ...
```

### 涉及文件

- `backend/app/agent_graph.py` — `stream_mode`、`conditional_edges`、`ToolNode` 格式

---

## 7. PostgreSQL 连接池耗尽

### 现象

运行一段时间后聊天 API 返回 500 错误，日志显示 `connection is closed` 或 `too many clients already`。

### 根因分析

- `SQLAlchemy` async engine 默认连接池大小为 5，在高并发场景下耗尽
- `langgraph-checkpoint-postgres` 的 `PostgresSaver`/`PostgresStore` 每次操作创建独立连接，不复用 engine 连接池

### 解决方案

- 增加 `pool_size=20`, `max_overflow=10`
- 移除 `PostgresSaver`/`PostgresStore`，使用 `InMemorySaver` + 应用层持久化

### 涉及文件

- `backend/app/database.py` — engine 连接池配置
- `backend/app/main.py` — graph 编译选项

---

## 8. 前端 SSE 流式中断问题

### 现象

阅读文档时 SSE 流式响应中途断开，或长时间（>5 分钟）无响应超时。

### 根因分析

- Nginx 默认 `proxy_read_timeout` 为 60s，SSE 长连接超过后 Nginx 断开
- `requests` 同步 HTTP 库的超时机制不适用于 SSE 逐 token 流式

### 解决方案

- Nginx 配置增加 `proxy_read_timeout 300s`
- 前端使用 `fetch` + `ReadableStream` 处理 SSE，设置 `signal: AbortSignal.timeout(120000)`
- 后端流式发送时添加 `try/except` 捕获 `BrokenPipeError` / `ConnectionResetError`

### 涉及文件

- `nginx.conf` — `proxy_read_timeout`
- `frontend/src/api/chat.ts` — SSE `fetch` 超时配置
- `backend/app/routes/chat.py` — 流式发送异常处理

---

## 9. 高并发下 MilvusClient gRPC 连接争抢

### 现象

并发测试（20 并发）下 `delete` 操作从 0.35s 降级到 2.6s，`batch_delete` 降级到 23s。混合负载阶段所有操作超时失败。

### 根因分析

`get_vector_store()` 返回单一的 `Milvus` 单例，其 `_milvus_client` 被所有并发请求共享。`MilvusClient` 底层 gRPC 连接不是线程安全的，并发请求在单一 gRPC 流上争抢。

### 解决方案

本地化个人计算机 PC 小规模应用场景下，每请求创建独立的 `MilvusClient()`，使用完关闭：

```python
def _new_client():
    from pymilvus import MilvusClient
    return MilvusClient(uri=settings.milvus_uri)
```

生产环境下建议使用 Milvus Cluster 模式 + 连接池中间件。

### 性能对比

| 操作 | 单例共享 gRPC | 独立 client |
|------|--------------|-------------|
| delete (20 并发) | avg 2.6s | **avg 1.14s** |
| batch_delete | avg 36.9s | **avg 23.5s** |
| list_docs (读) | 14ms | 17ms（持平） |
| upload | 210ms | 174ms（持平） |

### 涉及文件

- `backend/app/vector_store.py` — `_new_client()` / `delete_document()` / `batch_delete_documents()`

---

## 10. 后台页面文档详情弹窗关闭交互问题

### 现象

点击文档详情弹窗的「关闭」按钮或弹窗外区域时无法关闭弹窗。

### 根因分析

`@click.stop` 阻止了事件传播，导致外部 `@click="closeDetail"` 无法触发。同时 `v-if="detailDoc"` 绑定在 `Teleport` 的包装 `div` 上，关闭后组件被销毁但 `Teleport` 目标可能未正确清理。

### 解决方案

```vue
<!-- 外层点击关闭 -->
<div v-if="detailDoc" class="fixed inset-0 ..." @click="closeDetail">
  <!-- 内层阻止传播 -->
  <div class="..." @click.stop>
```

确保：
1.  最外层 `div` 的 `@click` 绑定 `closeDetail`
2.  内层卡片 `div` 使用 `@click.stop`
3.  `closeDetail` 中清理 PDF blob URL 等资源
