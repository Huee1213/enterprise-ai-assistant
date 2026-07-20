import asyncio
import time
from datetime import datetime, timezone
from fastapi import APIRouter
import httpx
from app.models import HealthStatus, ServiceStatus
from app.config import settings

_start_time = time.time()

router = APIRouter(tags=["Health"])


async def _tcp_check(host: str, port: int, timeout: float = 3) -> tuple[bool, str]:
    """Async TCP connectivity check via asyncio."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True, f"port {port} open"
    except asyncio.TimeoutError:
        return False, f"connect to {host}:{port} timed out"
    except Exception as e:
        return False, str(e)[:60]


async def _redis_check(timeout: float = 3) -> tuple[bool, str]:
    """Async Redis PING via raw TCP."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("redis", 6379), timeout=timeout
        )
        writer.write(b"PING\r\n")
        resp = await asyncio.wait_for(reader.read(1024), timeout=timeout)
        writer.close()
        await writer.wait_closed()
        if b"PONG" in resp:
            return True, "connected"
        return False, f"unexpected response: {resp[:20]}"
    except asyncio.TimeoutError:
        return False, "redis ping timed out"
    except Exception as e:
        return False, str(e)[:50]


async def _searxng_check(timeout: float = 5) -> tuple[bool, str]:
    """Async SearXNG health check via httpx."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                "http://searxng:8080/search?q=test&format=json",
                headers={"User-Agent": "HealthCheck/1.0"},
            )
            if resp.status_code == 200:
                return True, f"HTTP {resp.status_code}"
            return False, f"HTTP {resp.status_code}"
    except httpx.TimeoutException:
        return False, "searxng request timed out"
    except Exception as e:
        return False, str(e)[:50]


@router.get("/health", response_model=HealthStatus)
async def health_check():
    overall_timeout = 8  # total timeout for all checks combined

    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                _tcp_check("milvus", 19530, timeout=3),
                _redis_check(timeout=3),
                _searxng_check(timeout=5),
            ),
            timeout=overall_timeout,
        )
        milvus_ok, milvus_info = results[0]
        redis_ok, redis_info = results[1]
        searxng_ok, searxng_info = results[2]
    except asyncio.TimeoutError:
        milvus_ok = redis_ok = searxng_ok = False
        milvus_info = redis_info = searxng_info = "health check timed out"

    uptime = time.time() - _start_time
    local_now = datetime.now().astimezone()
    tz_offset = local_now.strftime("%z")
    tz_name = time.tzname[0 if time.daylight == 0 else 1]
    now_str = f"{local_now.strftime('%Y-%m-%d %H:%M:%S')} {tz_name} (UTC{tz_offset[:3]}:{tz_offset[3:] or '00'})"

    services = [
        ServiceStatus(name="Milvus", status="connected" if milvus_ok else "disconnected", info=milvus_info),
        ServiceStatus(name="Redis", status="connected" if redis_ok else "disconnected", info=redis_info),
        ServiceStatus(name="SearXNG", status="connected" if searxng_ok else "disconnected", info=searxng_info),
        ServiceStatus(name="LLM", status="configured" if settings.llm_api_key else "not configured", info=settings.llm_model),
    ]

    return HealthStatus(
        status="healthy" if (milvus_ok and redis_ok) else "degraded",
        version="1.0.0",
        server_time=now_str,
        uptime_seconds=round(uptime, 1),
        services=services,
        llm_configured=bool(settings.llm_api_key),
        milvus_connected=milvus_ok,
        redis_connected=redis_ok,
    )
