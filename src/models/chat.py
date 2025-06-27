"""
Data models for chat sessions and messages
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SessionStatus(str, Enum):
    """Session status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class ChatMessageCreate(BaseModel):
    """Model for creating a new chat message"""
    role: MessageRole
    content: str = Field(..., max_length=10000)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """Chat message data model"""
    id: Optional[int] = None
    session_id: str
    role: MessageRole
    content: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class ChatSessionCreate(BaseModel):
    """Model for creating a new chat session"""
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatSession(BaseModel):
    """Chat session data model"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: Optional[str] = None
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    message_count: int = Field(default=0)
    
    class Config:
        use_enum_values = True


class ChatContext(BaseModel):
    """Model for chat context with recent messages"""
    session_id: str
    messages: List[ChatMessage]
    total_messages: int
    context_window: int = Field(default=5)


class ChatRequest(BaseModel):
    """Model for chat API requests"""
    message: str = Field(..., max_length=10000)
    stream: bool = Field(default=False)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0, le=4000)


class ChatResponse(BaseModel):
    """Model for chat API responses"""
    message_id: Optional[int] = None
    session_id: str
    content: str
    role: MessageRole = Field(default=MessageRole.ASSISTANT)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SessionListResponse(BaseModel):
    """Model for listing chat sessions"""
    sessions: List[ChatSession]
    total: int
    page: int = Field(default=1)
    page_size: int = Field(default=50)


class SessionHistoryResponse(BaseModel):
    """Model for session history responses"""
    session: ChatSession
    messages: List[ChatMessage]
    total_messages: int


class OpenRouterMessage(BaseModel):
    """Model for OpenRouter API messages"""
    role: str
    content: str


class OpenRouterChatRequest(BaseModel):
    """Model for OpenRouter API chat requests"""
    model: str
    messages: List[OpenRouterMessage]
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=1000)
    stream: bool = Field(default=False)


class HealthCheck(BaseModel):
    """Model for health check responses"""
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    database_connected: bool
    temporal_connected: bool = Field(default=False)
    openrouter_connected: bool = Field(default=False)


class ErrorResponse(BaseModel):
    """Model for error responses"""
    error: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = None 