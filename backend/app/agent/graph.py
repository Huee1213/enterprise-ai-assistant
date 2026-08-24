"""LangChain 1.0 agent built with create_agent.

Uses LangChain 1.0's create_agent() factory instead of
manual StateGraph + ToolNode construction.
"""

import json
import asyncio
import logging
import time
from typing import AsyncGenerator

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.agent.tools import get_tools

logger = logging.getLogger(__name__)

# ── Runtime config cache ────────────────────────────────────────────────────
_effective_config: dict = {}
_config_loaded_at: float = 0
_CONFIG_TTL = 30


async def _load_effective_config() -> dict:
    global _effective_config, _config_loaded_at
    now = time.monotonic()
    if _effective_config and (now - _config_loaded_at) < _CONFIG_TTL:
        return _effective_config
    try:
        from app.agent.runtime_config import get_effective_config
        _effective_config = await get_effective_config()
    except Exception:
        _effective_config = {}
    _config_loaded_at = now
    return _effective_config


def _build_chat_model(cfg: dict):
    return ChatOpenAI(
        model=cfg.get("llm_model", settings.llm_model),
        temperature=float(cfg.get("llm_temperature", settings.llm_temperature)),
        max_tokens=int(cfg.get("llm_max_tokens", settings.llm_max_tokens)),
        api_key=cfg.get("llm_api_key", settings.llm_api_key) or settings.llm_api_key,
        base_url=cfg.get("llm_api_base", settings.llm_api_base) or settings.llm_api_base,
    )


def _build_agent():
    """Create a LangChain 1.0 agent with tools.
    
    System prompt is injected at invocation time so memory/context
    can be injected dynamically per-request.
    """
    return create_agent(
        model=_build_chat_model(_effective_config or {}),
        tools=get_tools(),
        name="enterprise_agent",
    )


DYNAMIC_SYSTEM = (
    "You are an enterprise AI knowledge assistant. "
    "Answer questions using the knowledge base when relevant. "
    "Always cite sources. Be concise."
)


def _build_messages(query: str, memory_context: str = "",
                    history_ctx: str = "") -> list:
    parts = [DYNAMIC_SYSTEM]
    if memory_context:
        parts.append(f"User context:\n{memory_context}")
    if history_ctx:
        parts.append(f"Recent conversation:\n{history_ctx}")
    return [
        {"role": "system", "content": "\n\n".join(parts)},
        {"role": "user", "content": query},
    ]


init_checkpointer = lambda: None
close_checkpointer = lambda: None


# ── Streaming helpers ──────────────────────────────────────────────────────


def _emit_reasoning(chunk) -> str:
    if hasattr(chunk, "content_blocks"):
        for block in chunk.content_blocks:
            if isinstance(block, dict) and block.get("type") == "reasoning":
                text = block.get("reasoning", "") or block.get("text", "")
                return text
    if hasattr(chunk, "usage_metadata") and hasattr(chunk.usage_metadata, "reasoning"):
        return getattr(chunk, "reasoning_content", "") or ""
    return getattr(chunk, "reasoning_content", "") or ""


# ── RAG streaming (no tool loop) ───────────────────────────────────────────


async def stream_rag(query: str, memory_context: str = "",
                     history_ctx: str = "", db=None, user_id: str = "",
                     conv_id: str = "") -> AsyncGenerator[str, None]:
    try:
        cfg = await _load_effective_config()
        from app.vector.store import similarity_search
        llm = _build_chat_model(cfg)
        loop = asyncio.get_running_loop()
        docs = await loop.run_in_executor(None, similarity_search, query, int(cfg.get("top_k", settings.top_k)))
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
        async for chunk in llm.astream([SystemMessage(content=sys), HumanMessage(content=query)]):
            reasoning = _emit_reasoning(chunk)
            if reasoning:
                yield f"data: {json.dumps({'event': 'reasoning', 'data': reasoning})}\n\n"
            if chunk.content:
                full_answer += chunk.content
                yield f"data: {json.dumps({'event': 'token', 'data': chunk.content})}\n\n"

        # NOTE: fact extraction for the RAG path is handled once by
        # chat.py `_post_stream_tasks` (fires for both agent and RAG modes),
        # so doing it here too would double the LLM calls. Removed deliberately.

        yield f"data: {json.dumps({'event': 'done', 'data': ''})}\n\n"
    except (GeneratorExit, asyncio.CancelledError):
        pass
    except Exception:
        yield f"data: {json.dumps({'event': 'done', 'data': ''})}\n\n"


# ── Agent streaming (with tool loop via create_agent) ──────────────────────


async def stream_agent(query: str, conv_id: str, memory_context: str = "",
                       history_ctx: str = "", user_id: str = "",
                       db=None) -> AsyncGenerator[str, None]:
    cfg = await _load_effective_config()
    llm = _build_chat_model(cfg)
    agent = create_agent(
        model=llm,
        tools=get_tools(),
        name="enterprise_agent",
    )

    messages = _build_messages(query, memory_context, history_ctx)

    try:
        step_num = 0
        seen_tool_call_ids: set = set()
        tool_args_by_id: dict = {}   # tool_call_id -> normalized args
        async for chunk in agent.astream(
            {"messages": messages},
            stream_mode=["messages", "updates"],
            version="v2",
        ):
            if chunk["type"] == "messages":
                msg, _metadata = chunk["data"]
                if isinstance(msg, AIMessage):
                    # Streaming tokens — incremental content only, no step emission.
                    # Tool-call args in this stream are partial chunks, so llm_call
                    # steps are emitted from the complete updates stream below.
                    if hasattr(msg, "text") and msg.text:
                        yield f"data: {json.dumps({'event': 'token', 'data': msg.text})}\n\n"
                    elif isinstance(msg.content, str) and msg.content:
                        yield f"data: {json.dumps({'event': 'token', 'data': msg.content})}\n\n"
            elif chunk["type"] == "updates":
                for source, update in chunk["data"].items():
                    # Node key for the LLM turn is "model" in create_agent v1
                    # (older versions use "agent"); accept both.
                    if source in ("model", "agent"):
                        # Complete LLM turn: emit ONE llm_call step per final tool call,
                        # with fully-populated arguments (dedupe by tool_call.id).
                        for am in update.get("messages", []):
                            if not isinstance(am, AIMessage):
                                continue
                            for tc in (getattr(am, "tool_calls", None) or []):
                                tc_name = tc.get("name") or ""
                                if not tc_name:
                                    continue
                                tc_id = tc.get("id") or f"{tc_name}|{tc.get('index', '')}"
                                args = tc.get("args") or {}
                                if isinstance(args, str):
                                    try:
                                        args = json.loads(args)
                                    except Exception:
                                        pass
                                tool_args_by_id[tc_id] = args
                                if tc_id in seen_tool_call_ids:
                                    continue
                                seen_tool_call_ids.add(tc_id)
                                step_num += 1
                                step_data = {
                                    "step": step_num,
                                    "action": "llm_call",
                                    "name": tc_name,
                                    "input": json.dumps(args, ensure_ascii=False),
                                    "output": f"调用工具 {tc_name}",
                                    "duration_ms": 0,
                                    "ts": time.time(),
                                }
                                yield f"data: {json.dumps({'event': 'step', 'data': step_data})}\n\n"
                    elif source == "tools":
                        # Tool execution result — one step per ToolMessage, carrying
                        # the parameters it was invoked with (linked by tool_call_id).
                        for tool_msg in update.get("messages", []):
                            if hasattr(tool_msg, "content") and tool_msg.content:
                                step_num += 1
                                tc_link = getattr(tool_msg, "tool_call_id", "") or ""
                                args = tool_args_by_id.get(tc_link, {})
                                step_data = {
                                    "step": step_num,
                                    "action": "tool_execution",
                                    "name": getattr(tool_msg, "name", "") or "",
                                    "input": json.dumps(args, ensure_ascii=False)
                                              if isinstance(args, (dict, list)) else str(args),
                                    "output": str(tool_msg.content)[:200],
                                    "duration_ms": 0,
                                    "ts": time.time(),
                                }
                                yield f"data: {json.dumps({'event': 'step', 'data': step_data})}\n\n"
    except (GeneratorExit, asyncio.CancelledError):
        return
    except Exception as e:
        import traceback, sys as _sys
        traceback.print_exc(file=_sys.stderr)
        yield f"data: {json.dumps({'event': 'token', 'data': f'[处理出错: {str(e)[:100]}]'})}\n\n"

    yield f"data: {json.dumps({'event': 'done', 'data': conv_id})}\n\n"


# ── Non-streaming variants ─────────────────────────────────────────────────


async def run_rag(query: str, memory_context: str = "") -> dict:
    cfg = await _load_effective_config()
    llm = _build_chat_model(cfg)
    from app.vector.store import similarity_search
    loop = asyncio.get_running_loop()
    docs = await loop.run_in_executor(None, similarity_search, query, int(cfg.get("top_k", settings.top_k)))
    context = "\n\n".join(
        f"[Source: {d.metadata.get('source', 'Unknown')}]\n{d.page_content}" for d in docs
    ) if docs else "No relevant documents found."
    sys = f"You are an enterprise knowledge assistant.\n\nUser context:\n{memory_context}\n\nAnswer based on context:\n{context}"
    response = await llm.ainvoke([SystemMessage(content=sys), HumanMessage(content=query)])
    return {
        "answer": response.content,
        "sources": [
            {"source": d.metadata.get("source", "Unknown"), "content": d.page_content[:200]}
            for d in docs
        ],
    }


async def run_agent(query: str, memory_context: str = "", history_ctx: str = "",
                    conversation_id: str = "", user_id: str = "") -> dict:
    cfg = await _load_effective_config()
    llm = _build_chat_model(cfg)
    agent = create_agent(
        model=llm,
        tools=get_tools(),
        name="enterprise_agent",
    )

    messages = _build_messages(query, memory_context, history_ctx)
    result = await agent.ainvoke({"messages": messages})
    answer = result["messages"][-1].content if isinstance(result["messages"][-1], AIMessage) else str(result["messages"][-1])
    return {"conversation_id": conversation_id, "answer": answer, "steps": []}
