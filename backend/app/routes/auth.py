from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import (
    create_user, authenticate_user, create_access_token,
    get_current_user, require_admin, get_user_by_id,
    list_users, delete_user, UserPublic,
)
from app.memory import (
    get_user_preferences, update_user_preferences,
    get_user_facts, add_user_fact, build_memory_context,
    get_user_stats, update_user_stats as memory_update_user_stats,
    clear_user_memory,
    list_user_messages, list_user_facts, list_user_summaries,
    update_fact, delete_fact, update_summary, delete_summary,
    delete_messages_by_ids, ConversationHistory,
    delete_conversation as memory_delete_conversation,
    bulk_delete_conversations as memory_bulk_delete_conversations,
)
from app.auth import update_user as auth_update_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class PreferenceUpdate(BaseModel):
    preferences: dict


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user)
    return TokenResponse(
        access_token=token,
        user=UserPublic(**{k: v for k, v in user.items() if k != "password_hash"}),
    )


@router.post("/register", response_model=TokenResponse)
async def register(
    req: RegisterRequest,
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="密码至少4位")
    user_pub = await create_user(db, req.username, req.password, role="employee", display_name=req.display_name or req.username)
    user = await authenticate_user(db, req.username, req.password)
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=user_pub)


@router.get("/me", response_model=UserPublic)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_id(db, current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserPublic(**user)


@router.get("/preferences")
async def get_preferences(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_preferences(db, current_user["user_id"])


@router.put("/preferences")
async def update_preferences(
    req: PreferenceUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_user_preferences(db, current_user["user_id"], req.preferences)


@router.get("/memory-context")
async def memory_context(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"context": await build_memory_context(db, current_user["user_id"])}


@router.get("/users", response_model=list[UserPublic])
async def get_users(
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users = await list_users(db)
    return [UserPublic(**u) for u in users]


class UserUpdateRequest(BaseModel):
    display_name: str = None
    password: str = None


@router.get("/users/{user_id}/stats")
async def get_user_stats_route(
    user_id: str,
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_stats(db, user_id)


@router.put("/users/{user_id}")
async def update_user_route(
    user_id: str,
    req: UserUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ok = await auth_update_user(db, user_id, display_name=req.display_name, password=req.password)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"status": "updated", "id": user_id}


class StatsUpdateRequest(BaseModel):
    conversations: int = None
    messages: int = None
    facts: int = None
    summaries: int = None
    reset: bool = False


@router.put("/users/{user_id}/stats")
async def update_user_stats_route(
    user_id: str,
    req: StatsUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    data = req.model_dump(exclude_none=True)
    result = await memory_update_user_stats(db, user_id, data)
    return {"status": "updated", "overrides": result}


@router.post("/users/{user_id}/clear-data")
async def clear_user_data_route(
    user_id: str,
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    counts = await clear_user_memory(db, user_id)
    return {"status": "cleared", "deleted": counts}


# ── User data browsing ────────────────────────────────────

@router.get("/users/{user_id}/messages")
async def get_user_messages(
    user_id: str, search: str = "", limit: int = 50, offset: int = 0,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    return await list_user_messages(db, user_id, search, limit, offset)


class BulkMsgIds(BaseModel):
    message_ids: list[int]


@router.post("/users/{user_id}/messages/bulk-delete")
async def bulk_delete_messages(
    user_id: str, req: BulkMsgIds,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    n = await delete_messages_by_ids(db, req.message_ids, user_id)
    return {"status": "deleted", "count": n}


@router.delete("/users/{user_id}/messages/{msg_id}")
async def delete_single_message(
    user_id: str, msg_id: int,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete as _d
    r = await db.execute(_d(ConversationHistory).where(ConversationHistory.id == msg_id, ConversationHistory.user_id == user_id))
    await db.commit()
    if r.rowcount == 0:
        raise HTTPException(status_code=404, detail="消息不存在")
    return {"status": "deleted"}


class BulkConvIds(BaseModel):
    conversation_ids: list[str]


@router.delete("/users/{user_id}/conversations/{conv_id}")
async def delete_user_conversation(
    user_id: str, conv_id: str,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    await memory_delete_conversation(db, user_id, conv_id)
    return {"status": "deleted"}


@router.post("/users/{user_id}/conversations/bulk-delete")
async def bulk_delete_user_conversations(
    user_id: str, req: BulkConvIds,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    await memory_bulk_delete_conversations(db, user_id, req.conversation_ids)
    return {"status": "deleted", "count": len(req.conversation_ids)}


@router.get("/users/{user_id}/facts")
async def get_user_facts_route(
    user_id: str, search: str = "", limit: int = 50, offset: int = 0,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    return await list_user_facts(db, user_id, search, limit, offset)


@router.get("/users/{user_id}/summaries")
async def get_user_summaries_route(
    user_id: str, search: str = "", limit: int = 50, offset: int = 0,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    return await list_user_summaries(db, user_id, search, limit, offset)


class ContentUpdate(BaseModel):
    content: str


class SummaryUpdate(BaseModel):
    summary: str


@router.put("/users/{user_id}/facts/{fact_id}")
async def update_fact_route(
    user_id: str, fact_id: int, req: ContentUpdate,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    ok = await update_fact(db, fact_id, req.content, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="事实不存在")
    return {"status": "updated"}


@router.delete("/users/{user_id}/facts/{fact_id}")
async def delete_fact_route(
    user_id: str, fact_id: int,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    ok = await delete_fact(db, fact_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="事实不存在")
    return {"status": "deleted"}


@router.put("/users/{user_id}/summaries/{summary_id}")
async def update_summary_route(
    user_id: str, summary_id: int, req: SummaryUpdate,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    ok = await update_summary(db, summary_id, req.summary, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="摘要不存在")
    return {"status": "updated"}


@router.delete("/users/{user_id}/summaries/{summary_id}")
async def delete_summary_route(
    user_id: str, summary_id: int,
    admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    ok = await delete_summary(db, summary_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="摘要不存在")
    return {"status": "deleted"}


@router.delete("/users/{user_id}")
async def remove_user(
    user_id: str,
    admin_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ok = await delete_user(db, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"status": "deleted", "id": user_id}
