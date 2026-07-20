from fastapi import APIRouter, HTTPException, Depends, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import (
    create_user, authenticate_user, create_access_token,
    get_current_user, require_admin, require_super_admin, get_user_by_id,
    list_users, list_admins, delete_user, UserPublic,
    update_admin_permissions, ALL_PERMISSIONS, PERM_GROUPS, PERM_CHILDREN,
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
    employee_id: str = ""


class BatchImportRequest(BaseModel):
    employee_ids: list[str]
    default_password: str = "123456"


class CheckEmployeeIdsRequest(BaseModel):
    employee_ids: list[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class PreferenceUpdate(BaseModel):
    preferences: dict


class CreateAdminRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""
    employee_id: str = ""
    permissions: list[str] = []


class UpdatePermissionsRequest(BaseModel):
    permissions: list[str]


def _has_perm(user: dict, perm: str) -> bool:
    if user.get("is_super_admin", False):
        return True
    perms = user.get("permissions", [])
    if perm in perms:
        return True
    for parent, children in PERM_CHILDREN.items():
        if perm in children and parent in perms:
            return True
    return False


def _require_perm(perm: str):
    async def _check(admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
        from app.auth import get_user_by_id as _get_user
        user = await _get_user(db, admin_user["user_id"])
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        if not _has_perm(user, perm):
            raise HTTPException(status_code=403, detail="无权执行此操作")
        return user
    return _check


async def _require_view_data(admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> dict:
    from app.auth import get_user_by_id as _get_user
    user = await _get_user(db, admin_user["user_id"])
    if not user or not _has_perm(user, "users.view_data"):
        raise HTTPException(status_code=403, detail="无权查看用户数据")
    return user


async def _require_user_manage(admin_user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> dict:
    from app.auth import get_user_by_id as _get_user
    user = await _get_user(db, admin_user["user_id"])
    if not user or not _has_perm(user, "users.manage"):
        raise HTTPException(status_code=403, detail="无权管理用户")
    return user


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # Check if already logged in elsewhere
    from app.redis_client import get_stored_token
    try:
        existing = await get_stored_token(user["id"])
        if existing is not None:
            raise HTTPException(status_code=409, detail="该账户已在别处登录，是否重新登录？")
    except HTTPException:
        raise
    except Exception:
        pass

    token = create_access_token(user)
    from app.auth import ACCESS_TOKEN_EXPIRE_HOURS
    from app.redis_client import store_token
    try:
        await store_token(user["id"], token, int(ACCESS_TOKEN_EXPIRE_HOURS * 3600))
    except Exception:
        pass
    return TokenResponse(
        access_token=token,
        user=UserPublic(**{k: v for k, v in user.items() if k != "password_hash"}),
    )


@router.post("/force-login", response_model=TokenResponse)
async def force_login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user)
    from app.auth import ACCESS_TOKEN_EXPIRE_HOURS
    from app.redis_client import store_token
    try:
        await store_token(user["id"], token, int(ACCESS_TOKEN_EXPIRE_HOURS * 3600))
    except Exception:
        pass
    return TokenResponse(
        access_token=token,
        user=UserPublic(**{k: v for k, v in user.items() if k != "password_hash"}),
    )


@router.post("/register", response_model=TokenResponse)
async def register(
    req: RegisterRequest,
    admin_user: dict = Depends(_require_perm("users.create")),
    db: AsyncSession = Depends(get_db),
):
    user_pub = await create_user(db, req.username, req.password, role="employee", display_name=req.display_name or req.username, employee_id=req.employee_id or None)
    user = await authenticate_user(db, req.username, req.password)
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=user_pub)


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
):
    from app.auth import invalidate_sessions
    await invalidate_sessions(current_user["user_id"])
    return {"status": "ok", "message": "已退出登录"}


# ── Admin management (super_admin only) ──────────────────────

@router.get("/admins", response_model=list[UserPublic])
async def get_admins(
    admin_user: dict = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    admins = await list_admins(db)
    return [UserPublic(**u) for u in admins]


@router.post("/admins")
async def create_admin(
    req: CreateAdminRequest,
    admin_user: dict = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    user_pub = await create_user(
        db, req.username, req.password, role="admin",
        display_name=req.display_name or req.username,
        employee_id=req.employee_id or None,
    )
    if req.permissions:
        await update_admin_permissions(db, user_pub.id, req.permissions)
    return {"status": "created", "user": UserPublic(**user_pub.model_dump())}


@router.put("/admins/{user_id}/permissions")
async def set_admin_permissions(
    user_id: str, req: UpdatePermissionsRequest,
    admin_user: dict = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    ok = await update_admin_permissions(db, user_id, req.permissions)
    if not ok:
        raise HTTPException(status_code=404, detail="管理员不存在")
    return {"status": "updated", "permissions": req.permissions}


@router.get("/permissions")
async def list_permissions(
    admin_user: dict = Depends(require_admin),
):
    groups = PERM_GROUPS
    # Non-super-admin cannot see or assign system.admins.* permissions
    if not admin_user.get("is_super_admin", False):
        groups = [g for g in groups if g["group"] != "system.admins"]
    return {"groups": groups}


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


@router.post("/check-employee-ids")
async def check_employee_ids_route(
    req: CheckEmployeeIdsRequest,
    admin_user: dict = Depends(_require_perm("users.view")),
    db: AsyncSession = Depends(get_db),
):
    from app.auth import check_employee_ids as _check
    return await _check(db, req.employee_ids)


@router.post("/batch-import-file")
async def batch_import_file(
    file: UploadFile,
    admin_user: dict = Depends(_require_perm("users.import")),
    db: AsyncSession = Depends(get_db),
):
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="导入文件不能超过 10MB")
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="导入文件不能超过 10MB")
    content = raw.decode("utf-8", errors="replace")
    lines = [l.strip() for l in content.replace("\r\n", "\n").split("\n") if l.strip()]
    from app.auth import create_user as _create, check_employee_ids as _check
    existing = await _check(db, lines)
    results = []
    for eid in lines:
        if any(r["employee_id"] == eid and r["registered"] for r in existing):
            results.append({"employee_id": eid, "status": "skipped", "reason": "工号已存在"})
            continue
        try:
            user = await _create(db, username=eid, password="123456", employee_id=eid, display_name=eid)
            results.append({"employee_id": eid, "status": "created"})
        except Exception as e:
            results.append({"employee_id": eid, "status": "error", "reason": str(e)[:50]})
    return {"results": results, "total": len(results), "created": sum(1 for r in results if r["status"] == "created")}


@router.post("/batch-import")
async def batch_import_employees(
    req: BatchImportRequest,
    admin_user: dict = Depends(_require_perm("users.import")),
    db: AsyncSession = Depends(get_db),
):
    from app.auth import create_user as _create, check_employee_ids as _check
    existing = await _check(db, req.employee_ids)
    results = []
    for eid in req.employee_ids:
        if any(r["employee_id"] == eid and r["registered"] for r in existing):
            results.append({"employee_id": eid, "status": "skipped", "reason": "工号已存在"})
            continue
        try:
            user = await _create(db, username=eid, password=req.default_password, employee_id=eid, display_name=eid)
            results.append({"employee_id": eid, "status": "created"})
        except Exception as e:
            results.append({"employee_id": eid, "status": "error", "reason": str(e)[:50]})
    return {"results": results, "total": len(results), "created": sum(1 for r in results if r["status"] == "created")}


class BatchDeleteUsersRequest(BaseModel):
    user_ids: list[str]


@router.post("/batch-delete")
async def batch_delete_users_route(
    req: BatchDeleteUsersRequest,
    admin_user: dict = Depends(_require_perm("users.delete")),
    db: AsyncSession = Depends(get_db),
):
    from app.auth import batch_delete_users as _batch_delete
    count = await _batch_delete(db, req.user_ids, admin_user.get("is_super_admin", False))
    return {"status": "deleted", "count": count}


@router.get("/users", response_model=list[UserPublic])
async def get_users(
    admin_user: dict = Depends(_require_perm("users.view")),
    db: AsyncSession = Depends(get_db),
):
    users = await list_users(db)
    return [UserPublic(**u) for u in users]


# ── Self-service profile ──────────────────────────

class UserUpdateRequest(BaseModel):
    display_name: str = None
    password: str = None
    employee_id: str = None
    avatar_url: str = None
    phone: str = None


class ProfileUpdateRequest(BaseModel):
    display_name: str = None
    password: str = None
    avatar_url: str = None
    phone: str = None


@router.put("/profile")
async def update_self_profile(
    req: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.auth import update_user as _update
    ok = await _update(
        db, current_user["user_id"],
        display_name=req.display_name,
        password=req.password,
        avatar_url=req.avatar_url,
        phone=req.phone,
        # employee_id is intentionally excluded — only super_admin can change it
    )
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    user = await get_user_by_id(db, current_user["user_id"])
    return UserPublic(**user) if user else None


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import os, asyncio
    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像文件不能超过 5MB")
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "avatars")
    ext = os.path.splitext(file.filename or ".png")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        raise HTTPException(status_code=400, detail="不支持的图片格式")
    filename = f"{current_user['user_id']}{ext}"
    file_path = os.path.join(upload_dir, filename)
    raw_data = await file.read()
    if len(raw_data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像文件不能超过 5MB")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _save_avatar, upload_dir, file_path, raw_data)
    avatar_url = f"/api/files/avatars/{filename}"
    from app.auth import update_user as _update
    await _update(db, current_user["user_id"], avatar_url=avatar_url)
    return {"url": avatar_url, "status": "ok"}


def _save_avatar(upload_dir: str, file_path: str, raw_data: bytes):
    os.makedirs(upload_dir, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(raw_data)


@router.get("/users/{user_id}/stats")
async def get_user_stats_route(
    user_id: str,
    admin_user: dict = Depends(_require_perm("users.view_data")),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_stats(db, user_id)


@router.put("/users/{user_id}")
async def update_user_route(
    user_id: str,
    req: UserUpdateRequest,
    admin_user: dict = Depends(_require_perm("users.edit")),
    db: AsyncSession = Depends(get_db),
):
    ok = await auth_update_user(
        db, user_id,
        display_name=req.display_name, password=req.password,
        employee_id=req.employee_id, avatar_url=req.avatar_url,
        phone=req.phone,
    )
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
    admin_user: dict = Depends(_require_view_data),
    db: AsyncSession = Depends(get_db),
):
    data = req.model_dump(exclude_none=True)
    result = await memory_update_user_stats(db, user_id, data)
    return {"status": "updated", "overrides": result}


@router.post("/users/{user_id}/clear-data")
async def clear_user_data_route(
    user_id: str,
    admin_user: dict = Depends(_require_perm("users.delete")),
    db: AsyncSession = Depends(get_db),
):
    counts = await clear_user_memory(db, user_id)
    return {"status": "cleared", "deleted": counts}


# ── User data browsing ────────────────────────────────────
# All routes below require users.view_data permission

@router.get("/users/{user_id}/messages")
async def get_user_messages(
    user_id: str, search: str = "", limit: int = 50, offset: int = 0,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    return await list_user_messages(db, user_id, search, limit, offset)


class BulkMsgIds(BaseModel):
    message_ids: list[int]


@router.post("/users/{user_id}/messages/bulk-delete")
async def bulk_delete_messages(
    user_id: str, req: BulkMsgIds,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    n = await delete_messages_by_ids(db, req.message_ids, user_id)
    return {"status": "deleted", "count": n}


@router.delete("/users/{user_id}/messages/{msg_id}")
async def delete_single_message(
    user_id: str, msg_id: int,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
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
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    await memory_delete_conversation(db, user_id, conv_id)
    return {"status": "deleted"}


@router.post("/users/{user_id}/conversations/bulk-delete")
async def bulk_delete_user_conversations(
    user_id: str, req: BulkConvIds,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    await memory_bulk_delete_conversations(db, user_id, req.conversation_ids)
    return {"status": "deleted", "count": len(req.conversation_ids)}


@router.get("/users/{user_id}/facts")
async def get_user_facts_route(
    user_id: str, search: str = "", limit: int = 50, offset: int = 0,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    return await list_user_facts(db, user_id, search, limit, offset)


@router.get("/users/{user_id}/summaries")
async def get_user_summaries_route(
    user_id: str, search: str = "", limit: int = 50, offset: int = 0,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    return await list_user_summaries(db, user_id, search, limit, offset)


class ContentUpdate(BaseModel):
    content: str


class SummaryUpdate(BaseModel):
    summary: str


@router.put("/users/{user_id}/facts/{fact_id}")
async def update_fact_route(
    user_id: str, fact_id: int, req: ContentUpdate,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    ok = await update_fact(db, fact_id, req.content, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="事实不存在")
    return {"status": "updated"}


class BulkIds(BaseModel):
    ids: list[int]


@router.post("/users/{user_id}/facts/bulk-delete")
async def bulk_delete_facts_route(
    user_id: str, req: BulkIds,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete as _d
    from app.memory import MemoryFact
    cond = [MemoryFact.user_id == user_id]
    if req.ids:
        cond.append(MemoryFact.id.in_(req.ids))
    r = await db.execute(_d(MemoryFact).where(*cond))
    await db.commit()
    return {"status": "deleted", "count": r.rowcount}


@router.post("/users/{user_id}/summaries/bulk-delete")
async def bulk_delete_summaries_route(
    user_id: str, req: BulkIds,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete as _d
    from app.memory import ConversationSummary
    cond = [ConversationSummary.user_id == user_id]
    if req.ids:
        cond.append(ConversationSummary.id.in_(req.ids))
    r = await db.execute(_d(ConversationSummary).where(*cond))
    await db.commit()
    return {"status": "deleted", "count": r.rowcount}


@router.delete("/users/{user_id}/facts/{fact_id}")
async def delete_fact_route(
    user_id: str, fact_id: int,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    ok = await delete_fact(db, fact_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="事实不存在")
    return {"status": "deleted"}


@router.put("/users/{user_id}/summaries/{summary_id}")
async def update_summary_route(
    user_id: str, summary_id: int, req: SummaryUpdate,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    ok = await update_summary(db, summary_id, req.summary, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="摘要不存在")
    return {"status": "updated"}


@router.delete("/users/{user_id}/summaries/{summary_id}")
async def delete_summary_route(
    user_id: str, summary_id: int,
    admin_user: dict = Depends(_require_perm("users.view_data")), db: AsyncSession = Depends(get_db),
):
    ok = await delete_summary(db, summary_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="摘要不存在")
    return {"status": "deleted"}


@router.delete("/users/{user_id}")
async def remove_user(
    user_id: str,
    admin_user: dict = Depends(_require_perm("users.delete")),
    db: AsyncSession = Depends(get_db),
):
    ok = await delete_user(db, user_id, admin_user.get("is_super_admin", False))
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"status": "deleted", "id": user_id}
