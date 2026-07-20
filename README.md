# 企业 AI 知识助手

> **生产级全栈企业知识库智能问答 Agent，基于 LangChain + LangGraph + Milvus + PostgreSQL + Vue 3，支持用户认证、角色权限与长短期记忆。**

---

## 🎯 功能特性

- **🔐 用户认证与角色权限** — JWT 双角色（管理员/员工），管理员管理知识库与用户，员工使用问答
- **🔑 细粒度权限系统** — 13 项权限（文档/用户/系统/Agent 分组），权限修改即时生效，无需重新登录
- **🔐 Redis 令牌管理** — 多设备登录冲突检测，支持强制登录（409 弹窗 + 401 跨设备踢出）
- **🔧 智能体配置管理** — 可视化配置 LLM（供应商/模型/密钥/Temperature）、向量嵌入（支持本地 ONNX / 远程 / 与 LLM 一致）、检索参数、Agent 行为
- **🔐 密钥安全存储** — API Key 全程掩码处理，保存后不可查看明文
- **📄 文档上传与 RAG 管道** — 支持 PDF/DOCX/TXT/MD/CSV，单文件 500MB 上限，支持多文件批量上传
- **🗑️ 文档多选删除** — 支持逐条删除和批量删除（`POST /api/documents/batch-delete`）
- **🤖 LangGraph Agent 工作流** — 状态机编排，多工具推理（知识检索、网页搜索、时间查询、摘要生成）
- **🔍 本地搜索引擎 (SearXNG)** — 自托管元搜索引擎，聚合 Google/Bing/Brave/Startpage 等，无需 API Key
- **🧠 长短期记忆系统** — PostgreSQL 持久化，偏好/事实/对话历史/自动摘要
- **⚡ 实时流式输出** — SSE 逐 Token 流式传输 + Markdown 渲染 + 推理步骤实时可见
- **📋 对话管理** — 单条消息删除+二次确认、重新生成、复制、编辑问题
- **🔍 历史对话搜索** — 侧栏搜索框按标题过滤历史对话
- **🎯 对话内搜索跳转** — Ctrl+F 搜索当前对话消息内容，上下逐条跳转，高亮定位
- **📖 文档预览** — 原始内容(含 PDF 内联/DOCX 样式/CSV 表格) + 文本块详情
- **🔎 Agent 调试面板** — 管理员可实时查看每步推理（LLM 调用、工具执行、输入输出）
- **📱 响应式布局** — 桌面端侧栏可缩边（仅图标），移动端滑出式侧栏 + Agent 面板
- **🌙 深色模式** — 持久主题切换，支持系统偏好检测
- **🐳 一键 Docker 部署** — 8 个容器一键启动
- **🔒 安全加固** — JWT 密钥必需环境变量；密码哈希与 JWT 密钥解耦；路径遍历防护；文件上传大小限制（文档 100MB / 头像 5MB）；异常信息防泄漏；异步线程池卸载阻塞操作

---

## 🧱 技术栈

| 层级 | 技术 |
|-------|-----------|
| **后端** | Python 3.11+, FastAPI, Uvicorn |
| **LLM 框架** | LangChain, LangGraph（状态机） |
| **向量数据库** | Milvus 2.5（langchain-milvus） |
| **结构化数据库** | PostgreSQL 16 + pgvector |
| **缓存** | Redis (valkey) |
| **LLM 提供商** | LiteLLM（OpenAI / DeepSeek / Anthropic / OpenRouter 等） |
| **搜索引擎** | SearXNG（自托管元搜索引擎） |
| **前端** | Vue 3 + TypeScript + Vite |
| **样式** | Tailwind CSS, CSS 变量（shadcn/ui 风格） |
| **状态管理** | Pinia |
| **认证** | JWT（pyjwt）+ SHA256 |
| **API 客户端** | Axios, Server-Sent Events |
| **DOCX 预览** | mammoth.js（浏览器端 DOCX → HTML 转换） |
| **部署** | Docker, docker-compose, Nginx |

---

## 📁 项目结构

```
enterprise-ai-assistant/
├── backend/                      # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + 生命周期
│   │   ├── config.py            # 环境变量配置
│   │   ├── models.py            # Pydantic 数据模型
│   │   ├── database.py          # SQLAlchemy 2.0 async + PostgreSQL
│   │   ├── auth.py              # JWT 认证、Redis 令牌管理
│   │   ├── redis_client.py      # Redis 连接、Token CRUD、在线状态
│   │   ├── memory.py            # 长短期记忆系统（SQLAlchemy ORM）
│   │   ├── embeddings.py        # 向量化（FastEmbed 本地）
│   │   ├── vector_store.py      # Milvus 向量存储
│   │   ├── document_processor.py # 文件解析与分块
│   │   ├── document_registry.py # 文档元数据 + 文本块存储
│   │   ├── tools.py             # LangChain 工具（知识/网页/时间/摘要）
│   │   ├── agent_graph.py       # LangGraph 状态机 + Agent
│   │   └── routes/
│   │       ├── auth.py          # 登录/注册/用户管理
│   │       ├── chat.py          # 流式/简单聊天 + 对话历史
│   │       ├── documents.py     # 文档上传/详情/预览（仅 admin）
│   │       ├── agent_config.py  # 智能体配置 CRUD
│   │       └── health.py        # 健康检查
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                     # Vue 3 + TypeScript 前端
│   ├── src/
│   │   ├── main.ts              # 应用入口
│   │   ├── App.vue              # 根组件 + 退出登录遮罩
│   │   ├── router/index.ts      # 路由 + 守卫
│   │   ├── stores/              # Pinia（chat, auth, theme, health）
│   │   ├── api/                 # API 客户端 + SSE 流式
│   │   ├── types/               # TypeScript 类型定义
│   │   ├── components/
│   │   │   ├── chat/            # ChatMessage, ChatInput, ChatContainer
│   │   │   ├── documents/       # DocumentUpload, DocumentList
│   │   │   ├── layout/          # Sidebar, ThemeToggle
│   │   │   ├── agent/           # AgentPanel（实时推理预览）
│   │   │   └── common/          # ConfirmDialog（通用确认弹窗）
│   │   └── views/
│   │       ├── ChatView.vue     # 员工/管理员聊天工作台
│   │       ├── LoginView.vue    # 登录
│   │       ├── AdminLayout.vue  # 管理后台布局
│   │       ├── AdminDashboard.vue # 系统总览
│   │       ├── AdminAgentConfig.vue # 智能体配置管理
│   │       ├── AdminUsers.vue   # 用户管理
│   │       └── DocumentsView.vue # 文档管理（上传/详情/预览）
│   ├── Dockerfile
│   └── package.json
├── searxng/                      # SearXNG 配置
│   ├── settings.yml              # （已 gitignore，需从 .example 复制）
│   └── settings.yml.example      # 示例配置
├── docker-compose.yml            # 8 服务编排
├── .env.example
└── README.md
```

---

## 🚀 快速开始（Docker）

### 前置条件

- Docker & Docker Compose v2
- **OpenAI 兼容 API Key**（OpenAI / DeepSeek / OpenRouter 等）

### 第一步：克隆与配置

```bash
git clone <仓库地址> enterprise-ai-assistant
cd enterprise-ai-assistant

cp .env.example .env

# SearXNG 配置文件（非必需，容器首次启动会自动生成默认配置）
cp searxng/settings.yml.example searxng/settings.yml
```

编辑 `.env` 文件：

```env
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=local/BAAI/bge-small-en-v1.5
```

### 第二步：启动所有服务

```bash
docker-compose up -d --build
```

| 服务 | 端口 | 描述 |
|---------|------|-------------|
| **PostgreSQL** | `5432` | 结构化数据库 |
| **Redis** | `6379` | 缓存 |
| **Milvus** | `19530` | 向量数据库 |
| **SearXNG** | `8080` | 元搜索引擎 |
| **后端 API** | `8000` | FastAPI + LangGraph Agent |
| **前端** | `80` | Vue SPA，Nginx 托管 |

### 第三步：验证部署

```bash
# 检查所有容器状态
docker-compose ps

# 后端健康检查
curl http://localhost:8000/health

# 默认管理员账号: admin / admin123
```

#### 预期响应：
```json
{
  "status": "healthy",
  "milvus_connected": true,
  "llm_configured": true
}
```

### 第四步：登录并上传文档

打开浏览器访问 `http://localhost`，使用以下账号登录：

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| `admin` | `admin123` | 管理员 | 文档管理、用户管理、系统监控 |

**管理员** 登录后：
1. 点击右上角 **后台** → **文档管理**
2. 拖拽或选择文件上传（支持批量、单文件最大 500MB）
3. 返回对话页面测试问答

### 第五步：测试聊天

```bash
curl -X POST http://localhost:8000/api/chat/simple \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <你的token>" \
  -d '{"message": "企业 AI 知识助手是什么？", "use_agent": false}'
```

---

## 📡 API 端点

| 方法 | 路径 | 认证 | 角色 | 描述 |
|--------|------|------|------|-------------|
| `POST` | `/api/auth/login` | — | — | 用户登录 |
| `POST` | `/api/auth/register` | JWT | admin | 注册员工 |
| `GET` | `/api/auth/me` | JWT | — | 当前用户信息 |
| `GET` | `/api/auth/users` | JWT | admin | 用户列表 |
| `PUT` | `/api/auth/users/{id}` | JWT | admin | 编辑用户 |
| `DELETE` | `/api/auth/users/{id}` | JWT | admin | 删除用户 |
| `GET` | `/api/auth/preferences` | JWT | — | 获取偏好 |
| `PUT` | `/api/auth/preferences` | JWT | — | 更新偏好 |
| `POST` | `/api/chat/stream` | JWT | — | 流式聊天（SSE） |
| `POST` | `/api/chat/simple` | JWT | — | 非流式聊天 |
| `POST` | `/api/chat/title` | JWT | — | 对话标题生成 |
| `GET` | `/api/chat/conversations` | JWT | — | 对话列表 |
| `GET` | `/api/chat/conversations/{id}` | JWT | — | 对话消息历史 |
| `DELETE` | `/api/chat/conversations/{id}` | JWT | — | 删除对话 |
| `GET` | `/api/chat/conversations/{id}/search?q=` | JWT | — | 搜索对话内消息
| `DELETE` | `/api/chat/conversations/{id}/messages/{mid}` | JWT | — | 删除单条消息 |
| `POST` | `/api/chat/conversations/{id}/messages/bulk-delete` | JWT | — | 批量删除消息 |
| `PUT` | `/api/chat/conversations/{id}/title` | JWT | — | 更新对话标题 |
| `POST` | `/api/documents/upload` | JWT | admin | 上传单文件 |
| `POST` | `/api/documents/upload-bulk` | JWT | admin | 批量上传 |
| `GET` | `/api/documents/list` | JWT | admin | 文档列表 |
| `GET` | `/api/documents/{id}` | JWT | admin | 文档详情+文本块 |
| `GET` | `/api/documents/{id}/file` | JWT | admin | 下载原文件 |
| `DELETE` | `/api/documents/{id}` | JWT | admin | 删除单个文档 |
| `POST` | `/api/documents/batch-delete` | JWT | admin | 批量删除文档 |
| `GET` | `/api/agent/config` | JWT | `agent.config` | 读取智能体配置 |
| `PUT` | `/api/agent/config` | JWT | `agent.config` | 保存配置覆盖项 |
| `POST` | `/api/agent/config/reset` | JWT | `agent.config` | 恢复默认配置 |
| `POST` | `/api/agent/config/fetch-models` | JWT | `agent.config` | 获取供应商模型列表 |
| `GET` | `/health` | — | — | 健康检查 |

---

## 🔧 配置参考

| 环境变量 | 默认值 | 描述 |
|---------------------|---------|-------------|
| `LLM_API_KEY` | — | LLM API 密钥（**必需**） |
| `LLM_MODEL` | `gpt-4o-mini` | LLM 模型名称 |
| `LLM_API_BASE` | `https://api.openai.com/v1` | API 基础 URL |
| `LLM_TEMPERATURE` | `0.1` | LLM 温度参数 |
| `LLM_MAX_TOKENS` | `4096` | 最大 Token 数 |
| `EMBEDDING_MODEL` | `local/BAAI/bge-small-en-v1.5` | 向量化模型 |
| `EMBEDDING_API_KEY` | — | 嵌入 API 密钥（远程模式） |
| `LLM_PROVIDER` | `openai` | 默认 LLM 供应商 |
| `JWT_SECRET_KEY` | **必需** | JWT 签名密钥（`openssl rand -hex 32` 生成） |
| `PASSWORD_SALT` | `enterprise-ai-password-salt-v1` | 密码哈希固定盐值 |
| `TZ` | `Asia/Shanghai` | 时区 |
| `MILVUS_URI` | `http://milvus:19530` | Milvus 连接地址 |
| `SEARXNG_URL` | `http://searxng:8080` | SearXNG 搜索地址 |
| `DB_URL` | `postgresql+asyncpg://app:app123@postgres:5432/enterprise_ai` | 数据库连接 |
| `CHUNK_SIZE` | `1000` | 文档分块大小 |
| `CHUNK_OVERLAP` | `200` | 分块重叠长度 |
| `TOP_K` | `5` | 检索返回块数 |

---

## 🏗️ 系统架构

```
┌──────────────┐     ┌──────────────┐     ┌─────────────────────────┐
│   浏览器     │────▶│    Nginx     │────▶│    FastAPI              │
│  (Vue 3)     │◀────│  (端口 80)    │◀────│  (端口 8000)            │
│  · 员工工作台 │     └──────────────┘     │  · JWT 认证              │
│  · 管理后台   │                           │  · LangGraph Agent       │
│  · 登录      │                           │  · 长短期记忆             │
│  · 文档管理   │                           │  · 文档管理               │
└──────────────┘                           │  · 智能体配置管理          │
                                           └──────────┬──────────────┘
                                                      │
             ┌────────────────────────────────────────┼───────────────────────┐
             │                    │                    │                       │
       ┌─────▼──────┐     ┌──────▼───────┐     ┌──────▼──────┐     ┌───────▼────────┐
       │ PostgreSQL │     │   Milvus    │     │   SearXNG   │     │    LLM API     │
       │ (pgvector)  │     │  (向量库)    │     │ (元搜索引擎)  │     │   (OpenAI)     │
       │ 用户/记忆   │     │              │     │              │     │                │
       │ 对话/会话   │     └──────────────┘     └──────┬───────┘     └────────────────┘
       └────────────┘                                  │
                                              ┌────────┴────────┐
                                              │ Google/Bing/ ... │
                                              └─────────────────┘
```

### Agent 工作流（LangGraph）

```
用户提问 → [LLM 推理] ──调用工具──→ [知识检索/网页搜索/时间查询/摘要]
               │                              │
               │  ← 工具结果 ────────────────┘
               │
               ▼
         [流式输出最终答案] → 用户
```

---

## 🔐 权限系统

| 路由 | 员工 | 管理员 |
|------|------|--------|
| `/` 聊天工作台 | ✅ | ✅ |
| `/admin` 后台总览 | — | ✅ |
| `/admin/agent` 智能体配置 | — | ✅ |
| `/admin/documents` 文档管理 | — | ✅ |
| `/admin/users` 用户管理 | — | ✅ |

---

## 🧠 记忆系统

| 类型 | 存储位置 | 说明 |
|------|---------|------|
| **短期记忆** | PostgreSQL `conversation_history` 表 | 当前对话窗口 + 自动摘要（每 6 条） |
| **长期事实** | PostgreSQL `memory_facts` 表 | 用户关键信息，含关键词自动提取 |
| **对话摘要** | PostgreSQL `conversation_summaries` 表 | 历史对话定期压缩摘要 |
| **用户偏好** | PostgreSQL `users.preferences` 字段 | JSON 格式个人设置 |

Agent 每次调用时自动注入用户记忆上下文到 system prompt。

---

## 📝 许可

All Rights Reserved. 本项目仅用于查看和参考，未经版权所有者明确书面许可，禁止任何形式的个人或商业使用、复制、修改、分发或部署。
