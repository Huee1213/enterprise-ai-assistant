import time
from datetime import datetime, timezone
from fastapi import APIRouter
from app.models import HealthStatus, ServiceStatus
from app.config import settings

_start_time = time.time()

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthStatus)
async def health_check():
    # Milvus check
    milvus_ok = False
    milvus_info = ""
    try:
        import socket
        s = socket.create_connection(("milvus", 19530), timeout=3)
        s.close()
        milvus_ok = True
        milvus_info = "port 19530 open"
    except Exception as e:
        milvus_info = str(e)[:60]

    # Redis check
    redis_ok = False
    redis_info = ""
    try:
        import socket
        s = socket.create_connection(("redis", 6379), timeout=3)
        s.sendall(b"PING\r\n")
        resp = s.recv(1024)
        if b"PONG" in resp:
            redis_ok = True
            redis_info = "connected"
        s.close()
    except Exception as e:
        redis_info = str(e)[:50]

    # SearXNG check
    searxng_ok = False
    searxng_info = ""
    try:
        import urllib.request
        req = urllib.request.Request("http://searxng:8080/search?q=test&format=json",
            headers={"User-Agent": "HealthCheck/1.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        if resp.status == 200:
            searxng_ok = True
        searxng_info = f"HTTP {resp.status}"
    except Exception as e:
        searxng_info = str(e)[:50]

    uptime = time.time() - _start_time
    import time as _time
    local_now = datetime.now().astimezone()
    tz_offset = local_now.strftime("%z")
    tz_name = _time.tzname[0 if _time.daylight == 0 else 1]
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
