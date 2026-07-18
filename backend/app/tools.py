import json
import urllib.request
import urllib.parse
from typing import List, Type
from langchain_core.tools import BaseTool
from langchain_core.documents import Document
from pydantic import BaseModel, Field
from app.vector_store import similarity_search


class KnowledgeSearchInput(BaseModel):
    query: str = Field(description="The search query to find relevant knowledge")


class KnowledgeSearchTool(BaseTool):
    name: str = "knowledge_search"
    description: str = "Search the enterprise knowledge base for relevant information. Use this when you need to answer questions based on uploaded documents."
    args_schema: Type[BaseModel] = KnowledgeSearchInput

    def _run(self, query: str) -> str:
        docs: List[Document] = similarity_search(query, k=5)
        if not docs:
            return "No relevant documents found in the knowledge base."

        results = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "Unknown")
            content = doc.page_content[:500]
            results.append(f"[Source {i+1}] ({source}):\n{content}")

        return "\n\n---\n\n".join(results)

    async def _arun(self, query: str) -> str:
        return self._run(query)


class WebSearchInput(BaseModel):
    query: str = Field(description="The web search query to find current information")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "Search the web for real-time information. Use this when you need current events, recent updates, or topics not covered in the knowledge base."
    args_schema: Type[BaseModel] = WebSearchInput

    def _get_searxng_url(self) -> str:
        import os
        return os.environ.get("SEARXNG_URL", "http://searxng:8080")

    def _run(self, query: str) -> str:
        try:
            searxng_url = self._get_searxng_url()
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
        return self._run(query)


class SummarizeInput(BaseModel):
    text: str = Field(description="The text to summarize")


class SummarizeTool(BaseTool):
    name: str = "summarize"
    description: str = "Summarize a given text. Use this when you need to condense long documents or conversation history."
    args_schema: Type[BaseModel] = SummarizeInput

    def _run(self, text: str) -> str:
        try:
            from langchain_openai import ChatOpenAI
            from app.config import settings
            llm = ChatOpenAI(
                model=settings.llm_model,
                temperature=0.3,
                max_tokens=300,
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base,
            )
            from langchain_core.messages import HumanMessage
            resp = llm.invoke([HumanMessage(content=f"Summarize the following text concisely:\n\n{text[:3000]}")])
            return resp.content
        except Exception as e:
            return f"Summary of text ({len(text)} chars):\n{text[:300]}..."


class GetCurrentTimeTool(BaseTool):
    name: str = "get_current_time"
    description: str = "Get the current date and time based on the server's deployment location. Use this when you need to know the current time, date, weekday, or timezone."
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


def get_tools() -> List[BaseTool]:
    return [
        KnowledgeSearchTool(),
        WebSearchTool(),
        SummarizeTool(),
        GetCurrentTimeTool(),
    ]
