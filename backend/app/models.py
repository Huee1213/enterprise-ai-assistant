from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class Role(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class Message(BaseModel):
    role: Role
    content: str
    timestamp: datetime = datetime.now()


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    use_agent: bool = True


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    sources: List[dict] = []


class DocumentInfo(BaseModel):
    id: str
    filename: str
    size: int
    content_type: str
    uploaded_at: datetime
    chunk_count: int = 0


class UploadResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: str


class AgentStep(BaseModel):
    step: int
    action: str
    input: str
    output: str
    duration_ms: float


class AgentDebugInfo(BaseModel):
    conversation_id: str
    query: str
    steps: List[AgentStep]
    final_answer: str
    total_duration_ms: float


class ServiceStatus(BaseModel):
    name: str
    status: str
    info: str = ""


class HealthStatus(BaseModel):
    status: str
    version: str
    server_time: str
    uptime_seconds: float
    services: List[ServiceStatus]
    llm_configured: bool
    milvus_connected: bool
    redis_connected: bool
