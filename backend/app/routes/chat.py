import json
import uuid
import asyncio
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatRequest, ChatResponse
from app.config import settings
from app.auth import get_current_user
from app.database import get_db, AsyncSessionLocal
from app.memory import build_memory_context, save_message, list_conversations, get_conversation_history, get_conversation_summary, delete_conversation, update_conversation_title, bulk_delete_conversations, ConversationHistory, add_user_fact, add_conversation_summary

router = APIRouter(prefix="/api/chat", tags=["Chat"])


class TitleRequest(BaseModel):
    message: str


class TitleResponse(BaseModel):
    title: str


async def _get_llm():
    """Build a ChatOpenAI from the effective (DB + env) config.

    Uses a clean async load so the configured model/key is respected
    even when called from an already-running event loop.
    """
    try:
        from app.agent.runtime_config import get_effective_config
        cfg = await get_effective_config()
    except Exception:
        cfg = {}
    model = cfg.get("llm_model", settings.llm_model)
    temp = float(cfg.get("llm_temperature", settings.llm_temperature))
    mt = int(cfg.get("llm_max_tokens", settings.llm_max_tokens))
    key = cfg.get("llm_api_key", settings.llm_api_key) or settings.llm_api_key
    base = cfg.get("llm_api_base", settings.llm_api_base) or settings.llm_api_base
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, temperature=temp, max_tokens=mt, api_key=key, base_url=base)


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.llm_api_key or settings.llm_api_key == "sk-your-key-here":
        raise HTTPException(status_code=500, detail="LLM API key not configured.")

    conv_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:8]}"
    user_id = current_user["user_id"]
    memory_ctx = await build_memory_context(db, user_id, conv_id)

    history = await get_conversation_history(db, user_id, conv_id, limit=10)
    history_ctx = ""
    if history:
        lines = []
        for h in history:
            role_label = "用户" if h["role"] == "user" else "助手"
            lines.append(f"{role_label}: {h['content'][:200]}")
        history_ctx = "\n".join(lines)
    conv_summary = await get_conversation_summary(db, user_id, conv_id)
    if conv_summary:
        summary_note = f"\n\n对话摘要: {conv_summary}"
        memory_ctx = memory_ctx + summary_note if memory_ctx else summary_note

    # Save user message and capture its DB ID for retry support
    user_msg_id = await save_message(db, user_id, conv_id, "user", request.message)

    if request.use_agent:
        from app.agent.graph import stream_agent
        generator = stream_agent(request.message, conv_id, memory_ctx, history_ctx=history_ctx, user_id=user_id, db=db)
    else:
        from app.agent.graph import stream_rag
        generator = stream_rag(request.message, memory_ctx, history_ctx=history_ctx, db=db, user_id=user_id, conv_id=conv_id)

    async def _post_stream_tasks(conv_id: str, user_msg: str, reply: str):
        """Background post-stream processing. LLM calls run in thread pool to not block event loop."""
        from app.database import AsyncSessionLocal
        import asyncio as _aio
        loop = _aio.get_running_loop()
        # ── LLM-based fact extraction (in thread pool) ──
        # Trigger gating lives inside generate_fact_from_message so there is a
        # single source of truth for when a fact should be extracted.
        if user_msg and reply:
            def _sync_fact(um: str, ar: str) -> str | None:
                from langchain_openai import ChatOpenAI
                from app.memory import generate_fact_from_message
                llm = ChatOpenAI(model=settings.llm_model, temperature=0.2, max_tokens=200, api_key=settings.llm_api_key, base_url=settings.llm_api_base)
                import asyncio as _a
                return _a.run(generate_fact_from_message(llm, um, ar))
            try:
                fact = await loop.run_in_executor(None, _sync_fact, user_msg, reply)
                if fact:
                    async with AsyncSessionLocal() as bg_db:
                        await add_user_fact(bg_db, user_id, fact)
            except Exception:
                pass
        # ── Summary generation (LLM, in a separate thread to not block the event loop) ──
        try:
            async with AsyncSessionLocal() as bg_db:
                hist = await get_conversation_history(bg_db, user_id, conv_id)
                existing = await get_conversation_summary(bg_db, user_id, conv_id)
                if len(hist) >= 10 and (len(hist) % 10 == 0 or not existing):
                    import asyncio as _aio
                    loop = _aio.get_running_loop()
                    context_parts = []
                    if existing:
                        context_parts.append(f"旧摘要: {existing}")
                    context_parts.append("最近对话:\n" + "\n".join(f"{'用户' if h['role']=='user' else 'AI'}: {h['content'][:800]}" for h in hist[-10:]))
                    context = "\n\n".join(context_parts)
                    def _sync_summary(context: str) -> str | None:
                        from langchain_openai import ChatOpenAI
                        from langchain_core.messages import SystemMessage, HumanMessage
                        llm = ChatOpenAI(model=settings.llm_model, temperature=0.3, max_tokens=500, api_key=settings.llm_api_key, base_url=settings.llm_api_base)
                        try:
                            import json
                            resp = llm.invoke([SystemMessage(content="你是一个对话摘要生成器。根据以下的对话内容，生成一段简洁完整的对话摘要，涵盖关键问题和回答。只输出摘要内容本身，不要前缀、不要引号。"), HumanMessage(content=context)])
                            s = resp.content.strip().strip('"').strip("'")
                            return s if len(s) > 5 else None
                        except Exception:
                            return None
                    summary = await loop.run_in_executor(None, _sync_summary, context)
                    if summary:
                        await add_conversation_summary(bg_db, user_id, conv_id, summary)
        except Exception:
            pass

    async def _stream_and_save():
        full_content = ""
        steps_data = []
        import asyncio as _asyncio
        try:
            async for event in generator:
                # Intercept done event — don't forward immediately
                is_done = event.startswith("data: ") and '"done"' in event
                if not is_done:
                    yield event
                try:
                    prefix = "data: "
                    if event.startswith(prefix):
                        parsed = json.loads(event[len(prefix):])
                        ev_type = parsed.get("event")
                        if ev_type == "token":
                            full_content += parsed.get("data", "")
                        elif ev_type == "step" or ev_type == "steps":
                            step_list = parsed.get("data", [])
                            if isinstance(step_list, dict):
                                step_list = [step_list]
                            for s in step_list:
                                if s not in steps_data:
                                    steps_data.append(s)
                        elif ev_type == "done":
                            if full_content:
                                meta = json.dumps({"steps": steps_data}, ensure_ascii=False) if steps_data else "{}"
                                assistant_id = await save_message(db, user_id, conv_id, "assistant", full_content, metadata_str=meta)
                                # Emit saved_msg_ids BEFORE done so frontend captures them
                                yield f"data: {json.dumps({'event': 'saved_msg_ids', 'data': {'user_msg_id': user_msg_id, 'assistant_msg_id': assistant_id}})}\n\n"
                                # Now forward the original done event
                                yield event
                                # Fire-and-forget fact extraction + summary generation
                                _asyncio.create_task(_post_stream_tasks(conv_id, request.message, full_content))
                except GeneratorExit:
                    raise
                except Exception:
                    pass
        except GeneratorExit:
            pass
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        _stream_and_save(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/simple", response_model=ChatResponse)
async def chat_simple(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.llm_api_key or settings.llm_api_key == "sk-your-key-here":
        raise HTTPException(status_code=500, detail="LLM API key not configured.")

    user_id = current_user["user_id"]
    conv_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:8]}"
    memory_ctx = await build_memory_context(db, user_id, conv_id)

    await save_message(db, user_id, conv_id, "user", request.message)

    if request.use_agent:
        from app.agent.graph import run_agent
        result = await run_agent(request.message, memory_ctx, conversation_id=conv_id, user_id=user_id)
        answer = result["answer"]
    else:
        from app.agent.graph import run_rag
        result = await run_rag(request.message, memory_ctx)
        answer = result["answer"]

    await save_message(db, user_id, conv_id, "assistant", answer)

    return ChatResponse(
        conversation_id=conv_id,
        answer=answer,
        sources=result.get("sources", []),
    )


@router.post("/title", response_model=TitleResponse)
async def generate_title(request: TitleRequest, current_user: dict = Depends(get_current_user)):
    title = request.message.strip()[:15] + ("..." if len(request.message) > 15 else "")
    if not title:
        return TitleResponse(title="新对话")
    try:
        if settings.llm_api_key and settings.llm_api_key != "sk-your-key-here":
            llm = await _get_llm()
            from langchain_core.messages import SystemMessage, HumanMessage
            prompt = (
                "根据用户的第一条消息和AI的回复，生成一个简洁的对话标题（3-8个字）。"
                "只输出标题本身，不要引号，不要多余文字。\n\n"
                f"{request.message}"
            )
            resp = await llm.ainvoke([
                SystemMessage(content="你是一个对话标题生成器。"),
                HumanMessage(content=prompt),
            ])
            t = resp.content.strip().strip('"').strip("'").split('\n')[0].strip()[:20]
            if 1 < len(t) <= 20 and len(t) < len(request.message):
                title = t
    except Exception:
        pass
    return TitleResponse(title=title)


@router.get("/suggestions")
async def chat_suggestions(
    current_user: dict = Depends(get_current_user),
    limit: int = 6,
):
    """Return starter questions derived from the knowledge base for the
    empty-chat state. No LLM call is made — questions are built from the
    uploaded documents in the registry."""
    from app.documents.registry import list_document_entries

    try:
        entries = list_document_entries() or []
    except Exception:
        entries = []

    suggestions = []
    if entries:
        def _ts(e: dict) -> datetime:
            try:
                return datetime.fromisoformat(str(e.get("uploaded_at", "")))
            except Exception:
                return datetime.min

        ordered = sorted(entries, key=_ts, reverse=True)
        for entry in ordered[: int(limit)]:
            filename = str(entry.get("filename") or "")
            stem = filename[: filename.rfind(".")] if "." in filename else filename
            stem = stem.strip() or "该文档"
            question = f"《{stem}》主要包含哪些内容？" if len(stem) <= 40 else "这份文档的主要内容是什么？"
            suggestions.append({
                "id": entry.get("id", ""),
                "title": f"《{stem}》",
                "question": question,
                "source": filename,
            })
        suggestions.insert(0, {
            "id": "__kb_overview__",
            "title": "知识库概览",
            "question": "知识库里有哪些文档？它们覆盖哪些主题？",
            "source": "",
        })

    return {"suggestions": suggestions, "total": len(suggestions), "empty": not entries}


# ── Conversation History API ───────────────────────────────────────────────

@router.get("/conversations")
async def get_conversations(
    search: str = "",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    convs = await list_conversations(db, current_user["user_id"])
    if search:
        q = search.lower().strip()
        convs = [c for c in convs if q in c.get("title", "").lower()]
    return {"conversations": convs}


@router.get("/conversations/{conv_id}")
async def get_conversation(
    conv_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msgs = await get_conversation_history(db, current_user["user_id"], conv_id)
    return {"conversation_id": conv_id, "messages": msgs}


@router.get("/conversations/{conv_id}/search")
async def search_conversation_messages(
    conv_id: str,
    q: str = "",
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msgs = await get_conversation_history(db, current_user["user_id"], conv_id)
    if not q:
        return {"conversation_id": conv_id, "matches": [], "query": q}
    query = q.lower().strip()
    matches = []
    for m in msgs:
        if query in m["content"].lower():
            matches.append({
                "id": m["id"],
                "role": m["role"],
                "timestamp": m["timestamp"],
                "snippet": m["content"][:100],
            })
    return {"conversation_id": conv_id, "matches": matches, "query": q}


@router.delete("/conversations/{conv_id}")
async def delete_conversation_route(
    conv_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await delete_conversation(db, current_user["user_id"], conv_id)
    return {"status": "deleted", "conversation_id": conv_id}


class BulkDeleteRequest(BaseModel):
    conversation_ids: list[str]


@router.post("/conversations/bulk-delete")
async def bulk_delete_conversations_route(
    req: BulkDeleteRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await bulk_delete_conversations(db, current_user["user_id"], req.conversation_ids)
    return {"status": "deleted", "count": len(req.conversation_ids)}


class TitleUpdate(BaseModel):
    title: str


@router.delete("/conversations/{conv_id}/messages")
async def clear_conversation_messages(
    conv_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(ConversationHistory).where(
        ConversationHistory.user_id == current_user["user_id"],
        ConversationHistory.conversation_id == conv_id,
    ))
    await db.commit()
    return {"status": "cleared", "conversation_id": conv_id}


@router.delete("/conversations/{conv_id}/messages/{msg_db_id}")
async def delete_single_message(
    conv_id: str,
    msg_db_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(ConversationHistory).where(
        ConversationHistory.id == msg_db_id,
        ConversationHistory.user_id == current_user["user_id"],
        ConversationHistory.conversation_id == conv_id,
    ))
    await db.commit()
    return {"status": "deleted", "message_id": msg_db_id}


@router.delete("/conversations/{conv_id}/messages/from/{msg_db_id}")
async def delete_messages_from(
    conv_id: str,
    msg_db_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete the specified message and all later messages in the conversation."""
    from sqlalchemy import delete as sql_delete, and_
    await db.execute(sql_delete(ConversationHistory).where(
        ConversationHistory.user_id == current_user["user_id"],
        ConversationHistory.conversation_id == conv_id,
        ConversationHistory.id >= msg_db_id,
    ))
    await db.commit()
    return {"status": "deleted", "from_id": msg_db_id}


class BulkMsgDeleteRequest(BaseModel):
    message_ids: list[int]


@router.post("/conversations/{conv_id}/messages/bulk-delete")
async def bulk_delete_messages(
    conv_id: str,
    req: BulkMsgDeleteRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(ConversationHistory).where(
        ConversationHistory.id.in_(req.message_ids),
        ConversationHistory.user_id == current_user["user_id"],
        ConversationHistory.conversation_id == conv_id,
    ))
    await db.commit()
    return {"status": "deleted", "count": len(req.message_ids)}


@router.post("/conversations/{conv_id}/regenerate-title")
async def regenerate_title(
    conv_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user["user_id"]
    from app.memory import get_conversation_summary
    summary = await get_conversation_summary(db, user_id, conv_id) or ""
    history = await get_conversation_history(db, user_id, conv_id, limit=6)
    context_parts = []
    if summary:
        context_parts.append(f"对话摘要: {summary}")
    if history:
        lines = [f"{'用户' if h['role']=='user' else 'AI'}: {h['content'][:200]}" for h in history[-4:]]
        context_parts.append("最近消息:\n" + "\n".join(lines))
    prompt = "\n\n".join(context_parts) if context_parts else "(无内容)"

    new_title = ""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        llm = ChatOpenAI(model=settings.llm_model, temperature=0.1, max_tokens=15, api_key=settings.llm_api_key, base_url=settings.llm_api_base)
        # Build a shorter, clearer prompt
        text_for_llm = summary[:100] if summary else ""
        if not text_for_llm and history:
            first = next((h["content"][:50] for h in history if h["role"] == "user"), "")
            text_for_llm = first
        if text_for_llm:
            resp = await llm.ainvoke([
                SystemMessage(content="你是标题生成器。只输出3-6个字的标题，不要解释。"),
                HumanMessage(content=f"为这段话生成标题: {text_for_llm}"),
            ])
            t = resp.content.strip().strip('"').strip("'").split('\n')[0].strip()[:15]
            if t and len(t) <= 12 and len(t) >= 2 and "标题" not in t and "生成" not in t:
                new_title = t
    except Exception:
        pass

    # Fallback to summary / first message
    if not new_title:
        if summary:
            new_title = summary[:12]
        elif history:
            first = next((h["content"][:12] for h in history if h["role"] == "user"), None)
            new_title = (first + "...") if first else "新对话"
        else:
            new_title = "新对话"

    await update_conversation_title(db, user_id, conv_id, new_title)
    return {"status": "regenerated", "title": new_title}


@router.put("/conversations/{conv_id}/title")
async def update_title(
    conv_id: str,
    req: TitleUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await update_conversation_title(db, current_user["user_id"], conv_id, req.title)
    return {"status": "updated", "title": req.title}
