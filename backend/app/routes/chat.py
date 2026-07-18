import json
import uuid
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatRequest, ChatResponse
from app.config import settings
from app.auth import get_current_user
from app.database import get_db
from app.memory import build_memory_context, save_message, list_conversations, get_conversation_history, delete_conversation, update_conversation_title, bulk_delete_conversations, ConversationHistory

router = APIRouter(prefix="/api/chat", tags=["Chat"])


class TitleRequest(BaseModel):
    message: str


class TitleResponse(BaseModel):
    title: str


def _get_llm():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base,
    )


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
    memory_ctx = await build_memory_context(db, user_id)

    # Load recent conversation history (last 10 messages) for context
    history = await get_conversation_history(db, user_id, conv_id, limit=10)
    history_ctx = ""
    if history:
        lines = []
        for h in history:
            role_label = "用户" if h["role"] == "user" else "助手"
            lines.append(f"{role_label}: {h['content'][:200]}")
        history_ctx = "\n".join(lines)

    # Save user message to history
    await save_message(db, user_id, conv_id, "user", request.message)

    if request.use_agent:
        from app.agent_graph import stream_agent
        generator = stream_agent(request.message, conv_id, memory_ctx, history_ctx=history_ctx, user_id=user_id, db=db)
    else:
        from app.agent_graph import stream_rag
        generator = stream_rag(request.message, memory_ctx, history_ctx=history_ctx, db=db, user_id=user_id, conv_id=conv_id)

    async def _stream_and_save():
        full_content = ""
        steps_data = []
        async for event in generator:
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
                            await save_message(db, user_id, conv_id, "assistant", full_content, metadata_str=meta)
                            # Auto-extract facts from user query
                            try:
                                from app.memory import add_user_fact
                                q = request.message.lower()
                                fact_kw = ["记住", "我叫", "我是", "我的名字", "我喜欢", "remember", "my name", "i am", "i like"]
                                for kw in fact_kw:
                                    if kw in q:
                                        idx = q.index(kw)
                                        fact = request.message[idx:idx+100].split("\n")[0][:80]
                                        if fact:
                                            await add_user_fact(db, user_id, f"用户说: {fact}")
                                        break
                            except Exception:
                                pass
                            try:
                                from app.memory import add_conversation_summary
                                hist = await get_conversation_history(db, user_id, conv_id)
                                if len(hist) > 0 and len(hist) % 6 == 0:
                                    from langchain_openai import ChatOpenAI
                                    from langchain_core.messages import SystemMessage, HumanMessage
                                    llm = ChatOpenAI(model=settings.llm_model, temperature=0.3, max_tokens=200, api_key=settings.llm_api_key, base_url=settings.llm_api_base)
                                    text = "\n".join(f"{'用户' if h['role']=='user' else 'AI'}: {h['content'][:300]}" for h in hist[-6:])
                                    resp = await llm.ainvoke([SystemMessage(content="用30字以内概括这段对话。"), HumanMessage(content=text)])
                                    summary = resp.content.strip()[:100]
                                    if summary:
                                        await add_conversation_summary(db, user_id, conv_id, summary)
                            except Exception:
                                pass
            except Exception:
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
    memory_ctx = await build_memory_context(db, user_id)
    conv_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:8]}"

    await save_message(db, user_id, conv_id, "user", request.message)

    if request.use_agent:
        from app.agent_graph import run_agent
        result = await run_agent(request.message, memory_ctx, conversation_id=conv_id, user_id=user_id)
        answer = result["answer"]
    else:
        from app.agent_graph import run_rag
        result = await run_rag(request.message, memory_ctx)
        answer = result["answer"]

    await save_message(db, user_id, conv_id, "assistant", answer)

    return ChatResponse(
        conversation_id=conv_id,
        answer=answer,
        sources=result.get("sources", []),
    )


@router.post("/title", response_model=TitleResponse)
async def generate_title(request: TitleRequest):
    title = request.message.strip()[:15] + ("..." if len(request.message) > 15 else "")
    if not title:
        return TitleResponse(title="新对话")
    try:
        if settings.llm_api_key and settings.llm_api_key != "sk-your-key-here":
            llm = _get_llm()
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


# ── Conversation History API ───────────────────────────────────────────────

@router.get("/conversations")
async def get_conversations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    convs = await list_conversations(db, current_user["user_id"])
    return {"conversations": convs}


@router.get("/conversations/{conv_id}")
async def get_conversation(
    conv_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msgs = await get_conversation_history(db, current_user["user_id"], conv_id)
    return {"conversation_id": conv_id, "messages": msgs}


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


@router.put("/conversations/{conv_id}/title")
async def update_title(
    conv_id: str,
    req: TitleUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await update_conversation_title(db, current_user["user_id"], conv_id, req.title)
    return {"status": "updated", "title": req.title}
