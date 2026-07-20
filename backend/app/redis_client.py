import os
import json
from datetime import datetime, timezone
import redis.asyncio as redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


# Token key helpers
TOKEN_KEY_PREFIX = "token:"
ONLINE_KEY_PREFIX = "online:"


def _token_key(user_id: str) -> str:
    return f"{TOKEN_KEY_PREFIX}{user_id}"


def _online_key(user_id: str) -> str:
    return f"{ONLINE_KEY_PREFIX}{user_id}"


async def store_token(user_id: str, token: str, ttl_seconds: int):
    r = await get_redis()
    await r.setex(_token_key(user_id), ttl_seconds, token)
    await r.setex(_online_key(user_id), ttl_seconds, "1")


async def get_stored_token(user_id: str) -> str | None:
    r = await get_redis()
    return await r.get(_token_key(user_id))


async def remove_token(user_id: str):
    r = await get_redis()
    await r.delete(_token_key(user_id), _online_key(user_id))


async def is_user_online(user_id: str) -> bool:
    r = await get_redis()
    val = await r.get(_online_key(user_id))
    return val == "1"
