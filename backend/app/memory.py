import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, desc, Text, Column, String, Integer, DateTime, ForeignKey, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import Base


class MemoryFact(Base):
    __tablename__ = "memory_facts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    conv_id = Column(String(36), index=True)
    summary = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), default="新对话")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    msg_meta = Column("msg_meta", Text, default="{}")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


# ── Preferences ────────────────────────────────────────────────────────────

async def get_user_preferences(db: AsyncSession, user_id: str) -> dict:
    from app.database import UserModel
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if user and user.preferences:
        return json.loads(user.preferences)
    return {}


async def update_user_preferences(db: AsyncSession, user_id: str, preferences: dict) -> dict:
    from app.database import UserModel
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {}
    existing = json.loads(user.preferences) if user.preferences else {}
    existing.update(preferences)
    user.preferences = json.dumps(existing, ensure_ascii=False)
    await db.commit()
    return existing


# ── Facts (Long-term memory) ─────────────────────────────────────────────

async def add_user_fact(db: AsyncSession, user_id: str, fact: str) -> None:
    entry = MemoryFact(user_id=user_id, content=fact, timestamp=datetime.now(timezone.utc))
    db.add(entry)
    await db.commit()


async def get_user_facts(db: AsyncSession, user_id: str, limit: int = 50) -> List[str]:
    result = await db.execute(
        select(MemoryFact).where(MemoryFact.user_id == user_id).order_by(desc(MemoryFact.id)).limit(limit)
    )
    return [f.content for f in reversed(result.scalars().all())]


# ── Conversation Summaries ──────────────────────────────────────────────

async def add_conversation_summary(db: AsyncSession, user_id: str, conv_id: str, summary: str) -> None:
    entry = ConversationSummary(user_id=user_id, conv_id=conv_id, summary=summary, timestamp=datetime.now(timezone.utc))
    db.add(entry)
    await db.commit()


async def get_recent_summaries(db: AsyncSession, user_id: str, limit: int = 5) -> List[str]:
    result = await db.execute(
        select(ConversationSummary).where(ConversationSummary.user_id == user_id)
        .order_by(desc(ConversationSummary.id)).limit(limit)
    )
    return [s.summary for s in reversed(result.scalars().all())]


# ── Conversation History (Short-term/Medium-term memory) ───────────────

async def save_message(db: AsyncSession, user_id: str, conversation_id: str, role: str, content: str, metadata_str: str = "{}") -> None:
    from sqlalchemy import text as _sql_text
    # Auto-create conversation record if not exists
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    if not result.scalar_one_or_none():
        db.add(Conversation(id=conversation_id, user_id=user_id, title="新对话", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
        await db.flush()
    # Save the actual message with metadata using raw SQL to ensure msg_meta is set
    await db.execute(
        _sql_text("INSERT INTO conversation_history (user_id, conversation_id, role, content, msg_meta, timestamp) VALUES (:uid, :cid, :role, :content, :meta, :ts)"),
        {"uid": user_id, "cid": conversation_id, "role": role, "content": content, "meta": metadata_str, "ts": datetime.now(timezone.utc)},
    )
    await db.commit()


async def update_conversation_title(db: AsyncSession, user_id: str, conversation_id: str, title: str) -> None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    conv = result.scalar_one_or_none()
    if conv:
        conv.title = title
        conv.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def get_conversation_history(db: AsyncSession, user_id: str, conversation_id: str, limit: int = 50) -> List[dict]:
    result = await db.execute(
        select(ConversationHistory).where(
            ConversationHistory.user_id == user_id,
            ConversationHistory.conversation_id == conversation_id,
        ).order_by(ConversationHistory.id).limit(limit)
    )
    return [
        {"id": r.id, "role": r.role, "content": r.content, "metadata": r.msg_meta or "{}", "timestamp": r.timestamp.isoformat()}
        for r in result.scalars().all()
    ]


async def list_conversations(db: AsyncSession, user_id: str) -> List[dict]:
    """List conversations with titles sorted by latest activity."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT c.id, c.title, COALESCE(ch.latest, c.updated_at) as latest
            FROM conversations c
            LEFT JOIN (
                SELECT conversation_id, MAX(timestamp) as latest
                FROM conversation_history
                GROUP BY conversation_id
            ) ch ON ch.conversation_id = c.id
            WHERE c.user_id = :uid
            ORDER BY latest DESC
            LIMIT 50
        """),
        {"uid": user_id},
    )
    return [{"conversation_id": r[0], "title": r[1] or "新对话", "latest": r[2].isoformat()} for r in result.all()]


async def delete_conversation(db: AsyncSession, user_id: str, conversation_id: str) -> None:
    await db.execute(delete(ConversationHistory).where(ConversationHistory.user_id == user_id, ConversationHistory.conversation_id == conversation_id))
    await db.execute(delete(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    await db.commit()


async def bulk_delete_conversations(db: AsyncSession, user_id: str, conversation_ids: list) -> None:
    for conv_id in conversation_ids:
        await db.execute(delete(ConversationHistory).where(ConversationHistory.user_id == user_id, ConversationHistory.conversation_id == conv_id))
        await db.execute(delete(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id))
    await db.commit()


# ── Memory Context Builder ─────────────────────────────────────────────

async def build_memory_context(db: AsyncSession, user_id: str) -> str:
    parts = []
    prefs = await get_user_preferences(db, user_id)
    if prefs:
        parts.append(f"用户偏好: {json.dumps(prefs, ensure_ascii=False)}")
    facts = await get_user_facts(db, user_id, 10)
    if facts:
        parts.append(f"长期记忆: {'; '.join(facts)}")
    summaries = await get_recent_summaries(db, user_id, 3)
    if summaries:
        parts.append(f"历史对话摘要: {'; '.join(summaries)}")
    return "\n".join(parts)
