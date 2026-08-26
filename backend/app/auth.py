import uuid
import json
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials as AuthorizationCredentials
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, UserModel, AsyncSessionLocal

_jwt_secret = __import__("os").environ.get("JWT_SECRET_KEY")
if not _jwt_secret:
    raise RuntimeError(
        "CRITICAL: JWT_SECRET_KEY environment variable is not set. "
        "Generate with: openssl rand -hex 32"
    )
SECRET_KEY = _jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
# Separate fixed salt for password hashing (changing JWT key should NOT invalidate passwords)
PASSWORD_SALT = "enterprise-ai-password-salt-v1"

security = HTTPBearer(auto_error=False)

# Permission blocks
PERM_DASHBOARD = "dashboard.view"
PERM_USER_VIEW = "users.view"
PERM_USER_CREATE = "users.create"
PERM_USER_EDIT = "users.edit"
PERM_USER_DELETE = "users.delete"
PERM_USER_IMPORT = "users.import"
PERM_USER_VIEW_DATA = "users.view_data"

PERM_DOC_VIEW = "documents.view"
PERM_DOC_UPLOAD = "documents.upload"
PERM_DOC_DELETE = "documents.delete"
PERM_DOC_DOWNLOAD = "documents.download"

PERM_ADMIN_VIEW = "system.admins.view"
PERM_ADMIN_MANAGE = "system.admins.manage"
PERM_AGENT_CONFIG = "agent.config"

ALL_PERMISSIONS = [
    PERM_DASHBOARD,
    PERM_DOC_VIEW, PERM_DOC_UPLOAD, PERM_DOC_DELETE, PERM_DOC_DOWNLOAD,
    PERM_USER_VIEW, PERM_USER_CREATE, PERM_USER_EDIT, PERM_USER_DELETE, PERM_USER_IMPORT, PERM_USER_VIEW_DATA,
    PERM_ADMIN_VIEW, PERM_ADMIN_MANAGE, PERM_AGENT_CONFIG,
]

# Parent → children mapping for legacy permissions
PERM_CHILDREN = {
    "users.manage": [PERM_USER_VIEW, PERM_USER_CREATE, PERM_USER_EDIT, PERM_USER_DELETE, PERM_USER_IMPORT],
    "documents.manage": [PERM_DOC_UPLOAD, PERM_DOC_DELETE],
}

PERM_GROUPS = [
    {
        "group": "dashboard",
        "label": "总览",
        "perms": [
            {"key": PERM_DASHBOARD, "label": "查看总览"},
        ],
    },
    {
        "group": "documents",
        "label": "知识库",
        "perms": [
            {"key": PERM_DOC_VIEW, "label": "查看文档"},
            {"key": PERM_DOC_UPLOAD, "label": "上传文档"},
            {"key": PERM_DOC_DELETE, "label": "删除文档"},
            {"key": PERM_DOC_DOWNLOAD, "label": "下载文件"},
        ],
    },
    {
        "group": "users",
        "label": "用户管理",
        "perms": [
            {"key": PERM_USER_VIEW, "label": "查看用户列表"},
            {"key": PERM_USER_CREATE, "label": "创建用户"},
            {"key": PERM_USER_EDIT, "label": "编辑用户"},
            {"key": PERM_USER_DELETE, "label": "删除用户"},
            {"key": PERM_USER_IMPORT, "label": "批量导入"},
            {"key": PERM_USER_VIEW_DATA, "label": "查看用户数据"},
        ],
    },
    {
        "group": "system.admins",
        "label": "管理员管理",
        "perms": [
            {"key": PERM_ADMIN_VIEW, "label": "查看管理员"},
            {"key": PERM_ADMIN_MANAGE, "label": "管理权限"},
        ],
    },
    {
        "group": "agent",
        "label": "智能体配置",
        "perms": [
            {"key": PERM_AGENT_CONFIG, "label": "管理 Agent 配置"},
        ],
    },
]


class UserPublic(BaseModel):
    id: str
    username: str
    role: str
    display_name: str
    created_at: str
    employee_id: Optional[str] = None
    avatar_url: str = ""
    phone: str = ""
    is_online: bool = False
    is_super_admin: bool = False
    permissions: list[str] = []


def _hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(f"{password}:{PASSWORD_SALT}".encode()).hexdigest()


def _generate_employee_id(prefix: str = "EMP") -> str:
    import random
    suffix = ''.join(random.choices("0123456789", k=6))
    return f"{prefix}-{suffix}"


def generate_strong_password(length: int = 12) -> str:
    """Generate a random password satisfying the app password policy:
    lower + upper + digit + special, min length 8."""
    import random
    lower = "abcdefghijklmnopqrstuvwxyz"
    upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digits = "0123456789"
    special = "!@#$%^&*()_+-=[]{};,.:?/"
    pool = lower + upper + digits + special
    length = max(8, int(length))
    pw = [
        random.choice(lower),
        random.choice(upper),
        random.choice(digits),
        random.choice(special),
    ]
    pw += [random.choice(pool) for _ in range(length - 4)]
    random.shuffle(pw)
    return "".join(pw)


def _validate_employee_id(eid: str) -> bool:
    import re
    return bool(re.match(r'^(EMP|ADM)-\d{6}$', eid))


def _parse_permissions(user) -> list[str]:
    if not user.permissions:
        return []
    try:
        return json.loads(user.permissions)
    except (json.JSONDecodeError, TypeError):
        return []


def _user_to_public(user) -> dict:
    perms = _parse_permissions(user)
    return {
        "id": user.id, "username": user.username, "role": user.role,
        "display_name": user.display_name or user.username,
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "employee_id": user.employee_id,
        "avatar_url": user.avatar_url or "",
        "phone": user.phone or "",
        "is_online": False,
        "is_super_admin": user.role == "super_admin",
        "permissions": perms,
    }


async def create_user(
    db: AsyncSession, username: str, password: str,
    role: str = "employee", display_name: str = "",
    employee_id: str = None, avatar_url: str = "", phone: str = "",
) -> UserPublic:
    import re
    if not username or len(username.strip()) < 3 or len(username) > 50:
        raise HTTPException(status_code=400, detail="用户名长度需在 3-50 个字符之间")
    if not re.match(r'^[a-zA-Z0-9_-]+$', username.strip()):
        raise HTTPException(status_code=400, detail="用户名只能包含字母、数字、下划线和连字符")
    if len(password) < 8 or len(password) > 128:
        raise HTTPException(status_code=400, detail="密码长度需在 8-128 个字符之间")
    if not re.search(r'[a-z]', password):
        raise HTTPException(status_code=400, detail="密码必须包含小写字母")
    if not re.search(r'[A-Z]', password):
        raise HTTPException(status_code=400, detail="密码必须包含大写字母")
    if not re.search(r'[0-9]', password):
        raise HTTPException(status_code=400, detail="密码必须包含数字")
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>\/?\\|]', password):
        raise HTTPException(status_code=400, detail="密码必须包含至少一个特殊字符")
    username = username.strip()
    if display_name and len(display_name) > 100:
        raise HTTPException(status_code=400, detail="显示名称不超过 100 个字符")
    result = await db.execute(select(UserModel).where(UserModel.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if employee_id:
        if not _validate_employee_id(employee_id):
            raise HTTPException(status_code=400, detail="工号格式：3-30位字母、数字和连字符，不能以连字符开头或结尾")
        result = await db.execute(select(UserModel).where(UserModel.employee_id == employee_id))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="工号已存在")
    else:
        prefix = "ADM" if role in ("admin", "super_admin") else "EMP"
        employee_id = _generate_employee_id(prefix)
        while True:
            result = await db.execute(select(UserModel).where(UserModel.employee_id == employee_id))
            if not result.scalar_one_or_none():
                break
            employee_id = _generate_employee_id(prefix)
    user = UserModel(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=_hash_password(password),
        role=role,
        display_name=display_name or username,
        employee_id=employee_id,
        avatar_url=avatar_url,
        phone=phone,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserPublic(**_user_to_public(user))


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[dict]:
    result = await db.execute(
        select(UserModel).where(or_(UserModel.username == username, UserModel.employee_id == username))
    )
    user = result.scalar_one_or_none()
    if user and user.password_hash == _hash_password(password):
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        return _user_to_public(user)
    return None


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[dict]:
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        pub = _user_to_public(user)
        from app.redis_client import is_user_online
        try:
            pub["is_online"] = await is_user_online(user_id)
        except Exception:
            pass
        return pub
    return None


def create_access_token(user: dict) -> str:
    import jwt, uuid
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    payload = {
        "jti": jti,
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "is_super_admin": user.get("is_super_admin", False),
        "permissions": user.get("permissions", []),
        "iat": now,
        "exp": now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
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
    token_str = credentials.credentials
    payload = decode_token(token_str)
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    # Redis token consistency check
    try:
        from app.redis_client import get_stored_token
        stored = await get_stored_token(payload["user_id"])
        if stored is not None and stored != token_str:
            raise HTTPException(status_code=401, detail="账号已在其他地方登录，请重新登录")
    except HTTPException:
        raise
    except Exception:
        import logging
        logging.getLogger(__name__).warning("Redis unavailable — skipping session validation")
    return payload


async def invalidate_sessions(user_id: str):
    from app.redis_client import remove_token
    try:
        await remove_token(user_id)
    except Exception:
        pass


async def refresh_user_online(user_id: str, ttl_seconds: int):
    from app.redis_client import get_redis
    from app.redis_client import ONLINE_KEY_PREFIX
    try:
        r = await get_redis()
        await r.setex(f"{ONLINE_KEY_PREFIX}{user_id}", ttl_seconds, "1")
    except Exception:
        pass


async def require_admin(current_user: dict = Security(get_current_user)) -> dict:
    role = current_user.get("role")
    if role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


async def require_super_admin(current_user: dict = Security(get_current_user)) -> dict:
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="需要系统管理员权限")
    return current_user


async def list_users(db: AsyncSession) -> list:
    result = await db.execute(
        select(UserModel).order_by(UserModel.created_at.desc())
    )
    users = result.scalars().all()
    pub_list = [_user_to_public(u) for u in users]
    from app.redis_client import is_user_online
    try:
        for pub in pub_list:
            pub["is_online"] = await is_user_online(pub["id"])
    except Exception:
        pass
    return pub_list


async def list_admins(db: AsyncSession) -> list:
    result = await db.execute(
        select(UserModel).where(UserModel.role.in_(["admin", "super_admin"])).order_by(UserModel.created_at.desc())
    )
    admins = result.scalars().all()
    return [_user_to_public(u) for u in admins]


async def update_user(
    db: AsyncSession, user_id: str, display_name: str = None,
    password: str = None, employee_id: str = None,
    avatar_url: str = None, phone: str = None,
) -> bool:
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return False
    if display_name is not None:
        user.display_name = display_name
    if password is not None:
        if len(password) < 8 or len(password) > 128:
            raise HTTPException(status_code=400, detail="密码长度需在 8-128 个字符之间")
        if not any(c.islower() for c in password):
            raise HTTPException(status_code=400, detail="密码必须包含小写字母")
        if not any(c.isupper() for c in password):
            raise HTTPException(status_code=400, detail="密码必须包含大写字母")
        if not any(c.isdigit() for c in password):
            raise HTTPException(status_code=400, detail="密码必须包含数字")
        import re
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>\/?\\|]', password):
            raise HTTPException(status_code=400, detail="密码必须包含至少一个特殊字符")
        user.password_hash = _hash_password(password)
    if employee_id is not None:
        if not _validate_employee_id(employee_id):
            raise HTTPException(status_code=400, detail="工号格式：3-30位字母、数字和连字符，不能以连字符开头或结尾")
        existing = await db.execute(select(UserModel).where(UserModel.employee_id == employee_id, UserModel.id != user_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="工号已被使用")
        user.employee_id = employee_id
    if avatar_url is not None:
        # Only allow external http(s) URLs, the internal upload path, or empty
        # (remove avatar). Blocks injection of arbitrary internal file routes.
        if avatar_url and not (
            avatar_url.startswith("/api/files/avatars/")
            or avatar_url.startswith("http://")
            or avatar_url.startswith("https://")
        ):
            raise HTTPException(status_code=400, detail="头像链接仅支持 http(s):// 地址或系统上传的头像")
        user.avatar_url = avatar_url
    if phone is not None:
        user.phone = phone
    await db.commit()
    return True


async def update_admin_permissions(db: AsyncSession, user_id: str, permissions: list[str]) -> bool:
    result = await db.execute(
        select(UserModel).where(UserModel.id == user_id, UserModel.role == "admin")
    )
    user = result.scalar_one_or_none()
    if not user:
        return False
    user.permissions = json.dumps(permissions)
    await db.commit()
    return True


async def delete_user(db: AsyncSession, user_id: str, is_super_admin: bool = False) -> bool:
    from sqlalchemy import delete as _d
    from app.memory import ConversationHistory
    from app.memory import Conversation as ConvModel
    from app.memory import MemoryFact
    from app.memory import ConversationSummary
    for tbl in [ConversationHistory, ConvModel, MemoryFact, ConversationSummary]:
        await db.execute(_d(tbl).where(tbl.user_id == user_id))
    role_filter = [UserModel.id == user_id]
    if not is_super_admin:
        role_filter.append(UserModel.role.notin_(["admin", "super_admin"]))
    result = await db.execute(
        select(UserModel).where(*role_filter)
    )
    user = result.scalar_one_or_none()
    if not user:
        await db.commit()
        return False
    await db.delete(user)
    await db.commit()
    return True


async def batch_delete_users(db: AsyncSession, user_ids: list[str], is_super_admin: bool = False) -> int:
    from sqlalchemy import delete as _d
    from app.memory import ConversationHistory
    from app.memory import Conversation as ConvModel
    from app.memory import MemoryFact
    from app.memory import ConversationSummary
    for tbl in [ConversationHistory, ConvModel, MemoryFact, ConversationSummary]:
        await db.execute(_d(tbl).where(tbl.user_id.in_(user_ids)))
    stmt = _d(UserModel).where(UserModel.id.in_(user_ids))
    if not is_super_admin:
        stmt = stmt.where(UserModel.role.notin_(["admin", "super_admin"]))
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def check_employee_ids(db: AsyncSession, employee_ids: list[str]) -> list:
    if not employee_ids:
        return []
    result = await db.execute(
        select(UserModel.employee_id).where(UserModel.employee_id.in_(employee_ids))
    )
    registered = {row[0] for row in result.fetchall()}
    return [
        {"employee_id": eid, "registered": eid in registered}
        for eid in employee_ids
    ]


async def init_admin():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserModel).where(UserModel.username == "admin"))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = UserModel(
                id=str(uuid.uuid4()),
                username="admin",
                password_hash=_hash_password("Admin@123"),
                role="super_admin",
                display_name="系统管理员",
                employee_id="ADM-000001",
                created_at=datetime.now(timezone.utc),
            )
            db.add(admin)
            await db.commit()
            return
        changed = False
        if admin.role != "super_admin":
            admin.role = "super_admin"
            admin.permissions = ""
            changed = True
        if not admin.display_name:
            admin.display_name = "系统管理员"
            changed = True
        # Normalize the built-in admin's employee id to the fixed initial value
        # (ADM-000001) when it is missing or still an auto-generated placeholder.
        cur_eid = admin.employee_id or ""
        if not cur_eid or cur_eid.startswith("EMP-"):
            admin.employee_id = "ADM-000001"
            changed = True
        if changed:
            await db.commit()
