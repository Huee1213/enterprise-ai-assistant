# 企业 AI 知识助手 — 产品概述

## 产品定位
企业 AI 知识助手是一款面向中大型企业的智能知识库问答系统，基于 RAG（检索增强生成）技术，帮助企业将内部的文档、知识库与 AI 大模型能力结合，实现自然语言驱动的知识查询与推理。

## 核心功能

### 1. 智能问答
- 基于 LangChain + LangGraph 的多轮对话
- 支持知识库检索、网页搜索、时间查询等多种工具
- 实时流式输出，逐 Token 显示

### 2. 知识库管理
- 支持 PDF / DOCX / TXT / MD / CSV 格式
- 自动分块与向量化
- Milvus 混合检索

### 3. 权限管理
- JWT 认证，支持管理员/员工双角色
- 管理员：文档管理、用户管理、系统监控
- 员工：智能问答、个人记忆

### 4. 记忆系统
- 长期记忆：用户偏好、事实存储
- 短期记忆：对话历史 + 自动摘要
- 跨会话持久化

## 技术架构

- 后端：Python 3.11 + FastAPI + LangChain + LangGraph
- 向量库：Milvus 2.5
- 数据库：PostgreSQL 16
- 搜索引擎：SearXNG
- 前端：Vue 3 + TypeScript + Tailwind CSS
- 部署：Docker Compose（8 个容器）

## 部署要求

- Docker & Docker Compose v2
- GPU：无要求（使用 CPU 推理）
- 内存：最低 8GB 推荐 16GB
- LLM API Key（支持 OpenAI / DeepSeek / 阿里云通义等）
