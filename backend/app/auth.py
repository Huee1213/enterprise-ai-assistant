import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials as AuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, UserModel, AsyncSessionLocal

SECRET_KEY = __import__("os").environ.get("JWT_SECRET_KEY", "enterprise-ai-secret-key-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer(auto_error=False)


class UserPublic(BaseModel):
    id: str
    username: str
    role: str
    display_name: str
    created_at: str


def _hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(f"{password}:{SECRET_KEY}".encode()).hexdigest()


async def create_user(
    db: AsyncSession, username: str, password: str,
    role: str = "employee", display_name: str = "",
) -> UserPublic:
    result = await db.execute(select(UserModel).where(UserModel.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = UserModel(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=_hash_password(password),
        role=role,
        display_name=display_name or username,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserPublic(
        id=user.id, username=user.username, role=user.role,
        display_name=user.display_name,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[dict]:
    result = await db.execute(select(UserModel).where(UserModel.username == username))
    user = result.scalar_one_or_none()
    if user and user.password_hash == _hash_password(password):
        return {
            "id": user.id, "username": user.username, "role": user.role,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat() if user.created_at else "",
            "preferences": user.preferences or "{}",
        }
    return None


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[dict]:
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        return {
            "id": user.id, "username": user.username, "role": user.role,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat() if user.created_at else "",
        }
    return None


def create_access_token(user: dict) -> str:
    import jwt
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    import jwt
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: AuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return payload


async def require_admin(current_user: dict = Security(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


async def list_users(db: AsyncSession) -> list:
    result = await db.execute(
        select(UserModel).order_by(UserModel.created_at.desc())
    )
    users = result.scalars().all()
    return [
        {"id": u.id, "username": u.username, "role": u.role,
         "display_name": u.display_name,
         "created_at": u.created_at.isoformat() if u.created_at else ""}
        for u in users
    ]


async def delete_user(db: AsyncSession, user_id: str) -> bool:
    result = await db.execute(
        select(UserModel).where(UserModel.id == user_id, UserModel.role != "admin")
    )
    user = result.scalar_one_or_none()
    if not user:
        return False
    await db.delete(user)
    await db.commit()
    return True


async def init_admin():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserModel).where(UserModel.username == "admin"))
        if not result.scalar_one_or_none():
            admin = UserModel(
                id=str(uuid.uuid4()),
                username="admin",
                password_hash=_hash_password("admin123"),
                role="admin",
                display_name="系统管理员",
                created_at=datetime.now(timezone.utc),
            )
            db.add(admin)
            await db.commit()
