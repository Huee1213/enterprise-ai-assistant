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
)

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
