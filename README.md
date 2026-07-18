# 企业 AI 知识助手

> **生产级全栈企业知识库智能问答 Agent，基于 LangChain + LangGraph + Milvus + Vue 3，支持用户认证、角色权限与长短期记忆。**

---

## 🎯 功能特性

- **🔐 用户认证与角色权限** — JWT 登录/注册，**管理员**(Admin) 管理知识库，**员工**(Employee) 使用问答
- **📄 文档上传与 RAG 管道** — 支持 PDF/DOCX/TXT/MD/CSV，自动分块向量化，Milvus 语义检索
- **🤖 LangGraph Agent 工作流** — 状态机编排，多工具推理（知识检索、网页搜索、摘要生成、当前时间）
- **🔍 本地搜索引擎 (SearXNG)** — 自托管元搜索引擎，聚合 Google/Bing/Brave/Startpage 等，无需 API Key
- **🧠 长短期记忆系统** — 用户偏好、长期事实、历史对话摘要，跨会话持久化
- **⚡ 实时流式输出** — SSE 逐 Token 流式传输 + Markdown 渲染
- **🔎 Agent 调试面板** — 实时查看每步推理（LLM 调用、工具执行、输入输出）
- **✏️ 编辑问题重新提问** — 修改已发送消息后自动重发
- **⏹️ 停止响应** — 流式输出时可随时中止
- **🌙 深色模式** — 持久主题切换，支持系统偏好检测
- **🐳 一键 Docker 部署** — 8 个容器一键启动

---

## 🧱 技术栈

| 层级 | 技术 |
|-------|-----------|
| **后端** | Python 3.11+, FastAPI, Uvicorn |
| **LLM 框架** | LangChain, LangGraph（状态机） |
| **向量数据库** | Milvus 2.5（langchain-milvus） |
| **LLM 供应商** | LiteLLM（OpenAI / DeepSeek / Anthropic 等） |
| **搜索引擎** | SearXNG（自托管元搜索引擎） |
| **前端** | Vue 3 + TypeScript + Vite |
| **样式** | Tailwind CSS, CSS 变量（shadcn/ui 风格） |
| **状态管理** | Pinia |
| **认证** | JWT（pyjwt）+ SHA256 |
| **API 客户端** | Axios, Server-Sent Events |
| **部署** | Docker, docker-compose, Nginx |

---

## 📁 项目结构

```
enterprise-ai-assistant/
├── backend/                      # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + 路由注册
│   │   ├── config.py            # 环境变量配置
│   │   ├── models.py            # Pydantic 数据模型
│   │   ├── auth.py              # JWT 认证、用户管理
│   │   ├── memory.py            # 长短期记忆系统
│   │   ├── embeddings.py        # 向量化（FastEmbed 本地）
│   │   ├── vector_store.py      # Milvus 向量存储
│   │   ├── document_processor.py # 文件解析与分块
│   │   ├── document_registry.py # 文档元数据管理
│   │   ├── tools.py             # LangChain 工具（知识/网页/时间/摘要）
│   │   ├── agent_graph.py       # LangGraph 状态机 + Agent
│   │   └── routes/
│   │       ├── auth.py          # 登录/注册/用户管理
│   │       ├── chat.py          # 流式/简单聊天
│   │       ├── documents.py     # 文档上传管理（仅 admin）
│   │       └── health.py        # 健康检查
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                     # Vue 3 + TypeScript 前端
│   ├── src/
│   │   ├── main.ts              # 应用入口
│   │   ├── App.vue              # 根组件
│   │   ├── router/index.ts      # 路由 + 守卫
│   │   ├── stores/              # Pinia（chat, auth, theme）
│   │   ├── api/                 # API 客户端 + 认证拦截器
│   │   ├── types/               # TypeScript 类型定义
│   │   ├── components/
│   │   │   ├── chat/            # ChatMessage, ChatInput, ChatContainer
│   │   │   ├── documents/       # DocumentUpload, DocumentList
│   │   │   ├── layout/          # Sidebar, ThemeToggle
│   │   │   └── agent/           # AgentPanel（实时推理预览）
│   │   └── views/
│   │       ├── ChatView.vue     # 员工工作台
│   │       ├── LoginView.vue    # 登录/注册
│   │       ├── AdminLayout.vue  # 管理后台布局
│   │       ├── AdminDashboard.vue # 总览
│   │       ├── AdminUsers.vue   # 用户管理
│   │       ├── DocumentsView.vue # 文档管理
│   │       └── AgentDebugView.vue # 调试面板
│   ├── Dockerfile
│   └── package.json
├── searxng/                      # SearXNG 配置
│   └── settings.yml
├── docker-compose.yml            # 6 服务编排
├── .env.example
├── documents/sample.md
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
| **前端** | `80` | Vue SPA，Nginx 托管 |
| **后端 API** | `8000` | FastAPI + LangGraph Agent |
| **Milvus** | `19530` | 向量数据库 |
| **SearXNG** | `8080` | 元搜索引擎 |
| **Redis** | `6379` | 搜索缓存 |

### 第三步：验证部署

```bash
# 检查容器状态
docker-compose ps

# 后端健康检查
curl http://localhost:8000/health

# 默认管理员账号
# 用户名: admin  密码: admin123
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
| `admin` | `admin123` | 管理员 | 文档管理、用户管理 |
| *(注册)* | — | 员工 | 对话问答 |

**管理员** 登录后：
1. 点击右上角 **管理后台**
2. 进入 **文档管理** 上传企业文档
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
| `POST` | `/api/auth/register` | — | — | 用户注册 |
| `GET` | `/api/auth/me` | JWT | — | 当前用户信息 |
| `GET` | `/api/auth/users` | JWT | admin | 用户列表 |
| `DELETE` | `/api/auth/users/{id}` | JWT | admin | 删除用户 |
| `GET` | `/api/auth/preferences` | JWT | — | 获取偏好 |
| `PUT` | `/api/auth/preferences` | JWT | — | 更新偏好 |
| `GET` | `/api/auth/memory-context` | JWT | — | 获取记忆上下文 |
| `POST` | `/api/chat/stream` | JWT | — | 流式聊天（SSE） |
| `POST` | `/api/chat/simple` | JWT | — | 非流式聊天 |
| `POST` | `/api/chat/title` | — | — | 对话标题生成 |
| `POST` | `/api/documents/upload` | JWT | admin | 上传文档 |
| `GET` | `/api/documents/list` | JWT | admin | 文档列表 |
| `DELETE` | `/api/documents/{id}` | JWT | admin | 删除文档 |
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
| `JWT_SECRET_KEY` | *(内置默认值)* | JWT 签名密钥 |
| `TZ` | `Asia/Shanghai` | 时区 |
| `MILVUS_URI` | `http://milvus:19530` | Milvus 连接地址 |
| `SEARXNG_URL` | `http://searxng:8080` | SearXNG 搜索地址 |
| `CHUNK_SIZE` | `1000` | 文档分块大小 |
| `CHUNK_OVERLAP` | `200` | 分块重叠长度 |
| `TOP_K` | `5` | 检索返回块数 |

---

## 🏗️ 架构架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   浏览器     │────▶│    Nginx     │────▶│    FastAPI       │
│  (Vue 3)     │◀────│  (端口 80)    │◀────│  (端口 8000)     │
│  · 员工工作台 │     └──────────────┘     │  · JWT 认证       │
│  · 管理后台   │                           │  · LangGraph Agent│
│  · 登录/注册  │                           │  · 长短期记忆      │
└──────────────┘                           └────────┬─────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────────┐
                    │                               │                   │
              ┌─────▼──────┐                ┌───────▼────────┐  ┌──────▼───────┐
              │   Milvus   │                │   SearXNG      │  │    LLM API  │
              │  (向量库)   │                │  (元搜索引擎)    │  │  (OpenAI)   │
              └────────────┘                └───────┬────────┘  └──────────────┘
                                                    │
                                         ┌──────────┴──────────┐
                                         │  Google / Bing /     │
                                         │  Brave / Startpage   │
                                         └─────────────────────┘
```

### Agent 工作流（LangGraph）

```
用户提问 → [LLM 推理] ──调用工具──→ [知识检索/网页搜索/时间/摘要]
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
| `/documents` 文档 | — | ✅ |
| `/agent-debug` 调试 | ✅ | ✅ |
| `/admin` 后台 | — | ✅ |
| `/admin/documents` 文档管理 | — | ✅ |
| `/admin/users` 用户管理 | — | ✅ |

---

## 🧠 记忆系统

| 类型 | 存储位置 | 说明 |
|------|---------|------|
| **短期记忆** | 当前对话上下文 | LLM 上下文窗口内 |
| **长期偏好** | `data/memory/{user_id}.json` | 用户个人设置 |
| **长期事实** | JSON 文件（最多 50 条） | 跨会话的用户关键信息 |
| **对话摘要** | JSON 文件（最多 20 条） | 历史对话总结 |

Agent 每次被调用时自动注入用户记忆上下文到 system prompt。

---

## 📝 许可

MIT
