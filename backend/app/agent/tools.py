import json
import asyncio
from typing import List, Type
from langchain_core.tools import BaseTool
from langchain_core.documents import Document
from pydantic import BaseModel, Field
from app.vector.store import similarity_search


class KnowledgeSearchInput(BaseModel):
    query: str = Field(description="The search query to find relevant knowledge")


class KnowledgeSearchTool(BaseTool):
    name: str = "knowledge_search"
    description: str = "Search the enterprise knowledge base for relevant information."
    args_schema: Type[BaseModel] = KnowledgeSearchInput
    top_k: int = 5
    score_threshold: float = 0.0

    def _run(self, query: str) -> str:
        # Fail fast with a clear, actionable message when the configured local
        # embedding model is not downloaded — otherwise FastEmbed would block
        # for minutes attempting its own (likely failing) download.
        try:
            from app.agent.runtime_config import get_effective_config_sync
            from app.vector.model_downloader import is_local_model_ready
            cfg = get_effective_config_sync()
            if (cfg.get("embedding_provider") == "local"
                    and cfg.get("embedding_model")
                    and not is_local_model_ready(cfg["embedding_model"])):
                return ("知识库检索暂不可用：本地嵌入模型尚未下载。"
                        "请管理员在 系统-智能体配置-向量嵌入 中下载该模型或更换嵌入供应商。")
        except Exception:
            pass
        docs: List[Document] = similarity_search(
            query,
            k=max(1, int(self.top_k)),
            threshold=float(self.score_threshold or 0.0),
        )
        if not docs:
            return "No relevant documents found in the knowledge base."
        results = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "Unknown")
            content = doc.page_content[:500]
            results.append(f"[Source {i+1}] ({source}):\n{content}")
        return "\n\n---\n\n".join(results)

    async def _arun(self, query: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run, query)


class WebSearchInput(BaseModel):
    query: str = Field(description="The web search query to find current information")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "Search the web for real-time information."
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str) -> str:
        try:
            import os
            import urllib.request
            import urllib.parse
            searxng_url = os.environ.get("SEARXNG_URL", "http://searxng:8080")
            params = urllib.parse.urlencode({"q": query, "format": "json"})
            req = urllib.request.Request(f"{searxng_url}/search?{params}",
                headers={"User-Agent": "Enterprise-AI-Assistant/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            results = data.get("results", [])
            if not results:
                suggestions = data.get("suggestions", [])
                if suggestions:
                    return f"No direct results found. Did you mean: {' | '.join(suggestions[:5])}?"
                return f"No web search results found for: {query}"
            lines = []
            for i, r in enumerate(results[:5]):
                title = r.get("title", "").strip()
                content = r.get("content", "").strip()
                url = r.get("url", "")
                engine = r.get("engine", "")
                lines.append(f"[{i+1}] {title}")
                if content:
                    lines.append(f"   {content[:200]}")
                lines.append(f"   URL: {url}  [{engine}]")
            return "\n".join(lines)
        except Exception as e:
            return f"Web search error: {str(e)}"

    async def _arun(self, query: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run, query)


class SummarizeInput(BaseModel):
    text: str = Field(description="The text to summarize")


class SummarizeTool(BaseTool):
    name: str = "summarize"
    description: str = "Summarize a given text."
    args_schema: Type[BaseModel] = SummarizeInput

    def _run(self, text: str) -> str:
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage
            from app.config import settings
            llm = ChatOpenAI(
                model=settings.llm_model,
                temperature=0.3,
                max_tokens=300,
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base,
            )
            resp = llm.invoke([HumanMessage(content=f"Summarize the following text concisely:\n\n{text[:3000]}")])
            return resp.content
        except Exception as e:
            return f"Summary of text ({len(text)} chars):\n{text[:300]}..."

    async def _arun(self, text: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run, text)


class GetCurrentTimeTool(BaseTool):
    name: str = "get_current_time"
    description: str = "Get the current date and time based on server timezone."
    args_schema: Type[BaseModel] = type("NoInput", (BaseModel,), {})

    def _run(self) -> str:
        from datetime import datetime
        import time
        now = datetime.now().astimezone()
        tz_name = time.tzname[0 if time.daylight == 0 else 1]
        offset = now.strftime('%z')
        weekday = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][now.weekday()]
        return (f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Weekday: {weekday}\n"
                f"Timezone: {tz_name} (UTC{offset[:3]}:{offset[3:] or '00'})")

    async def _arun(self) -> str:
        return self._run()


def get_tools(cfg: dict | None = None) -> List[BaseTool]:
    """Build the toolset honouring the effective agent config.

    Toggles (enable_web_search / enable_knowledge_search / enable_summarize /
    enable_time_tool) and top_k come from the saved config; when called from a
    thread (no running loop) the effective config is loaded from DB.
    """
    if cfg is None:
        cfg = _load_cfg_sync()
    cfg = cfg or {}
    def _flag(key: str, default: bool = True) -> bool:
        v = cfg.get(key)
        if isinstance(v, bool):
            return v
        return default

    tools: List[BaseTool] = []
    if _flag("enable_knowledge_search"):
        tools.append(KnowledgeSearchTool(
            top_k=int(cfg.get("top_k", 5) or 5),
            score_threshold=float(cfg.get("score_threshold", 0.0) or 0.0),
        ))
    if _flag("enable_web_search"):
        tools.append(WebSearchTool())
    if _flag("enable_summarize"):
        tools.append(SummarizeTool())
    if _flag("enable_time_tool"):
        tools.append(GetCurrentTimeTool())
    return tools


def _load_cfg_sync() -> dict:
    """Load effective config synchronously (safe to call from any thread)."""
    import asyncio as _a
    try:
        _a.get_running_loop()
    except RuntimeError:
        # Worker thread: run a dedicated loop.
        loop = _a.new_event_loop()
        try:
            from app.agent.runtime_config import get_effective_config
            return loop.run_until_complete(get_effective_config())
        finally:
            loop.close()
    return {}
