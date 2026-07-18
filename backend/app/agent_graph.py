"""Pure LangChain/LangGraph agent with tool calling and streaming.

Uses LangChain's component architecture:
  - StateGraph with MessagesState
  - ToolNode for tool execution
  - stream_mode="messages" for LLM token streaming
  - Simple RAG via vector_store
"""

import json
import asyncio
import logging
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

from app.config import settings
from app.tools import get_tools

logger = logging.getLogger(__name__)


def _get_llm():
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base,
    )


tools: list[BaseTool] = get_tools()
tool_node = ToolNode(tools)
llm = _get_llm().bind_tools(tools)


# ── Graph nodes ────────────────────────────────────────────────────────────


async def call_model(state: MessagesState) -> dict:
    system = SystemMessage(
        content="You are an enterprise AI knowledge assistant. "
                "Answer questions using the knowledge base when relevant. "
                "Always cite sources. Be concise."
    )
    msgs = [system] + list(state["messages"])
    try:
        response = llm.invoke(msgs)
    except Exception as e:
        err = str(e)
        if "ResourceExhausted" in err or "rate limit" in err.lower():
            response = AIMessage(content="抱歉，API 请求过于频繁，请稍后再试。")
        else:
            response = AIMessage(content=f"抱歉，处理请求时出现错误：{err[:100]}")
    return {"messages": [response]}


def should_continue(state: MessagesState):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


# ── Graph build ────────────────────────────────────────────────────────────

workflow = StateGraph(MessagesState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
workflow.add_edge("tools", "agent")
workflow.add_edge(START, "agent")

agent_graph = workflow.compile()

# Module-level flag: never attempt checkpointer connections
init_checkpointer = lambda: None
close_checkpointer = lambda: None


# ── Streaming helpers ──────────────────────────────────────────────────────


def _emit_reasoning(chunk) -> str:
    """Extract and return reasoning content from an LLM chunk if present."""
    if hasattr(chunk, "content_blocks"):
        for block in chunk.content_blocks:
            if isinstance(block, dict) and block.get("type") == "reasoning":
                text = block.get("reasoning", "") or block.get("text", "")
                return text
    if hasattr(chunk, "usage_metadata") and hasattr(chunk.usage_metadata, "reasoning"):
        return getattr(chunk, "reasoning_content", "") or ""
    return getattr(chunk, "reasoning_content", "") or ""


def _get_full_llm():
    """LLM with reasoning extraction support."""
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base,
    )


async def stream_rag(query: str, memory_context: str = "",
                     history_ctx: str = "", db=None, user_id: str = "",
                     conv_id: str = "") -> AsyncGenerator[str, None]:
    from app.vector_store import similarity_search
    temp_llm = _get_full_llm()
    docs = similarity_search(query, k=settings.top_k)
    context = "\n\n".join(
        f"[Source: {d.metadata.get('source', 'Unknown')}]\n{d.page_content}" for d in docs
    ) if docs else "No relevant documents found."

    sources = [
        {"source": d.metadata.get("source", "Unknown"), "content": d.page_content[:200]}
        for d in docs
    ]
    yield f"data: {json.dumps({'event': 'sources', 'data': sources})}\n\n"

    history_block = f"\n\nRecent conversation:\n{history_ctx}" if history_ctx else ""
    sys = f"You are an enterprise knowledge assistant.\n\nUser context:\n{memory_context}{history_block}\n\nAnswer based on the context below.\nContext:\n{context}"

    full_answer = ""
    async for chunk in temp_llm.astream([SystemMessage(content=sys), HumanMessage(content=query)]):
        reasoning = _emit_reasoning(chunk)
        if reasoning:
            yield f"data: {json.dumps({'event': 'reasoning', 'data': reasoning})}\n\n"
        if chunk.content:
            full_answer += chunk.content
            yield f"data: {json.dumps({'event': 'token', 'data': chunk.content})}\n\n"

    # Auto-extract facts for memory
    if db and user_id:
        try:
            from app.memory import add_user_fact
            fact_keywords = ["记住", "我叫", "我是", "我的名字", "我喜欢", "remember", "my name", "i am", "i like"]
            q_lower = query.lower()
            for kw in fact_keywords:
                if kw in q_lower:
                    idx = q_lower.index(kw)
                    fact = query[idx:idx + 100].split("\n")[0][:80]
                    if fact:
                        await add_user_fact(db, user_id, f"用户说: {fact}")
                        yield f"data: {json.dumps({'event': 'step', 'data': {'step': 0, 'action': 'memory', 'input': '', 'output': '已保存记忆: ' + fact, 'duration_ms': 0}})}\n\n"
                    break
        except Exception:
            pass

    yield f"data: {json.dumps({'event': 'done', 'data': ''})}\n\n"


async def stream_agent(query: str, conv_id: str, memory_context: str = "",
                       history_ctx: str = "", user_id: str = "", db=None) -> AsyncGenerator[str, None]:
    msgs = [SystemMessage(content="You are an enterprise AI knowledge assistant.")]
    if memory_context:
        msgs.append(SystemMessage(content=f"User context:\n{memory_context}"))
    if history_ctx:
        msgs.append(SystemMessage(content=f"Recent conversation:\n{history_ctx}"))
    msgs.append(HumanMessage(content=query))

    input_state = {"messages": msgs}

    try:
        step_num = 0
        async for update in agent_graph.astream(input_state, stream_mode="updates"):
            for node_name, state in update.items():
                if node_name == "agent":
                    last_msg = state["messages"][-1] if state.get("messages") else None
                    if not last_msg:
                        continue
                    if isinstance(last_msg, AIMessage):
                        if last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                step_num += 1
                                step_data = {
                                    "step": step_num,
                                    "action": "llm_call",
                                    "input": str(tc.get("args", {})),
                                    "output": f"Calling {tc.get('name', 'unknown')}...",
                                    "duration_ms": 0,
                                }
                                yield f"data: {json.dumps({'event': 'step', 'data': step_data})}\n\n"
                        if last_msg.content:
                            for i in range(0, len(last_msg.content), 3):
                                yield f"data: {json.dumps({'event': 'token', 'data': last_msg.content[i:i+3]})}\n\n"
                                await asyncio.sleep(0.003)
                elif node_name == "tools":
                    for tool_msg in state.get("messages", []):
                        if hasattr(tool_msg, "content") and tool_msg.content:
                            step_num += 1
                            step_data = {
                                "step": step_num,
                                "action": "tool_execution",
                                "input": "",
                                "output": str(tool_msg.content)[:200],
                                "duration_ms": 0,
                            }
                            yield f"data: {json.dumps({'event': 'step', 'data': step_data})}\n\n"
    except Exception as e:
        import traceback, sys as _sys
        traceback.print_exc(file=_sys.stderr)
        yield f"data: {json.dumps({'event': 'token', 'data': f'[处理出错: {str(e)[:100]}]'})}\n\n"

    yield f"data: {json.dumps({'event': 'done', 'data': conv_id})}\n\n"


async def run_rag(query: str, memory_context: str = "") -> dict:
    from app.vector_store import similarity_search
    temp_llm = _get_llm()
    docs = similarity_search(query, k=settings.top_k)
    context = "\n\n".join(
        f"[Source: {d.metadata.get('source', 'Unknown')}]\n{d.page_content}" for d in docs
    ) if docs else "No relevant documents found."
    sys = f"You are an enterprise knowledge assistant.\n\nUser context:\n{memory_context}\n\nAnswer based on context:\n{context}"
    response = await temp_llm.ainvoke([SystemMessage(content=sys), HumanMessage(content=query)])
    return {
        "answer": response.content,
        "sources": [
            {"source": d.metadata.get("source", "Unknown"), "content": d.page_content[:200]}
            for d in docs
        ],
    }


async def run_agent(query: str, memory_context: str = "", history_ctx: str = "", conversation_id: str = "", user_id: str = "") -> dict:
    msgs = [SystemMessage(content="You are an enterprise AI knowledge assistant.")]
    if memory_context:
        msgs.append(SystemMessage(content=f"User context:\n{memory_context}"))
    if history_ctx:
        msgs.append(SystemMessage(content=f"Recent conversation:\n{history_ctx}"))
    msgs.append(HumanMessage(content=query))
    result = await agent_graph.ainvoke({"messages": msgs})
    answer = result["messages"][-1].content if isinstance(result["messages"][-1], AIMessage) else str(result["messages"][-1])
    return {"conversation_id": conversation_id, "answer": answer, "steps": []}
