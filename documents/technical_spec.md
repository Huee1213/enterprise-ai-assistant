# 企业 AI 知识助手 — 技术规格书

## 系统架构

```
┌──────────────────────────────────────────────────┐
│               Nginx (反向代理)                    │
├──────────────────────────────────────────────────┤
│     FastAPI (Python 3.11) + Uvicorn              │
│     ├── LangChain (LLM 编排)                     │
│     ├── LangGraph (Agent 状态机)                 │
│     └── LiteLLM (多供应商 LLM 网关)              │
├──────────────────────────────────────────────────┤
│  PostgreSQL 16          │  Milvus 2.5            │
│  (用户/记忆/会话数据)     │  (向量检索)             │
├──────────────────────────────────────────────────┤
│  SearXNG (元搜索引擎)    │  Redis (缓存)           │
└──────────────────────────────────────────────────┘
```

## API 端点

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/login | 用户登录 |
| POST | /api/auth/register | 注册员工(需管理员) |
| GET  | /api/auth/me | 当前用户信息 |

### 聊天
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/chat/stream | 流式聊天(SSE) |
| POST | /api/chat/simple | 简单聊天 |
| POST | /api/chat/title | 生成对话标题 |

### 文档
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/documents/upload | 上传文档 |
| GET  | /api/documents/list | 文档列表 |
| GET  | /api/documents/{id} | 文档详情 |

## 数据模型

### 用户表 (users)
- id: UUID (PK)
- username: VARCHAR(100) UNIQUE
- password_hash: VARCHAR(128)
- role: VARCHAR(20) — 'admin' | 'employee'
- display_name: VARCHAR(100)
- preferences: TEXT (JSON)

### 对话历史 (conversation_history)
- id: SERIAL (PK)
- user_id: UUID → users(id)
- conversation_id: VARCHAR(36)
- role: VARCHAR(20)
- content: TEXT
- msg_meta: TEXT (JSON — steps, sources)

## 容器配置

| 服务 | 镜像 | 端口 |
|------|------|------|
| postgres | pgvector/pgvector:pg16 | 5432 |
| milvus | milvusdb/milvus:v2.5.0 | 19530 |
| redis | valkey/valkey:8-alpine | 6379 |
| searxng | searxng/searxng:latest | 8080 |
| backend | Dockerfile (python:3.11-slim) | 8000 |
| frontend | Dockerfile (node:20 → nginx) | 80 |

## 性能指标

- 单文档最大支持：50MB
- 支持并发用户数：≥ 100
- 平均响应时间（RAG 模式）：< 3s
- 向量检索返回 TOP-K：5
- 文档分块大小：1000 字符
