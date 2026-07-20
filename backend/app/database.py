import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, Text, Integer, DateTime, func

DB_URL = os.environ.get("DB_URL", "sqlite+aiosqlite:///app/data/app.db")

engine = create_async_engine(DB_URL, pool_size=10, max_overflow=20, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), nullable=False, default="employee")
    display_name = Column(String(100), default="")
    employee_id = Column(String(50), unique=True, nullable=True, index=True)
    avatar_url = Column(String(500), default="")
    phone = Column(String(30), default="")
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    preferences = Column(Text, default="{}")
    permissions = Column(Text, default="")  # JSON array for admin role permissions; empty = all/super_admin


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from sqlalchemy import text as _text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migration: add missing tables/columns
        migrations = [
            "ALTER TABLE conversation_summaries ADD COLUMN IF NOT EXISTS conv_id VARCHAR(36)",
            "CREATE TABLE IF NOT EXISTS conversations (id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE, title VARCHAR(200) DEFAULT '新对话', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
            "CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)",
            "ALTER TABLE conversation_history ADD COLUMN IF NOT EXISTS msg_meta TEXT DEFAULT '{}'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_id VARCHAR(50)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500) DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(30) DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions TEXT DEFAULT ''",
            "UPDATE users SET role = 'super_admin' WHERE username = 'admin'",
            "UPDATE users SET employee_id = CONCAT('EMP-', UPPER(SUBSTRING(MD5(id::text) FROM 1 FOR 6))) WHERE employee_id IS NULL OR employee_id = ''",
        ]
        for sql in migrations:
            try:
                await conn.execute(_text(sql))
            except Exception:
                pass
