# 企业 AI 知识助手 - 示例文档

## 概述

企业 AI 知识助手是一个全栈智能问答系统，融合了 LangChain、LangGraph 和 Milvus 向量数据库，提供企业级的文档理解与问答能力。

## 架构

### 前端
- Vue 3 + TypeScript + Vite 构建用户界面
- Tailwind CSS 样式框架
- 实时流式聊天界面
- 文档管理界面

### 后端
- FastAPI + Uvicorn API 服务器
- LangChain LLM 编排框架
- LangGraph Agent 状态机工作流
- Milvus 向量数据库语义搜索
- LiteLLM 多供应商 LLM 支持

### 核心功能

1. **文档上传与 RAG**
   - 支持 PDF、DOCX、TXT、MD、CSV 文件
   - 自动文本分块与向量化
   - Milvus 混合语义检索

2. **LangGraph Agent**
   - 状态机工作流编排
   - 多工具（知识检索、网页搜索、摘要）
   - 步骤级推理过程可视化

3. **流式响应**
   - SSE 实时 Token 流式传输
   - 来源与 Agent 步骤在界面中展示
   - Markdown 富文本渲染

## 快速开始

```bash
# 克隆仓库
git clone <仓库地址>
cd enterprise-ai-assistant

# 配置环境变量
cp .env.example .env
# 编辑 .env 设置你的 LLM_API_KEY

# 启动所有服务
docker-compose up -d

# 访问应用
# 前端: http://localhost
# 后端 API: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

## 使用说明

1. 通过文档管理页面上传企业文档
2. 用自然语言提问
3. AI Agent 检索知识库并给出精准答案
4. 在调试面板中查看 Agent 推理过程
