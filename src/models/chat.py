"""
Data models for chat sessions and messages
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator
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


class ToolCallStatus(str, Enum):
    """Tool call status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolCallParameter(BaseModel):
    """Model for tool call parameters"""
    name: str = Field(..., description="Parameter name")
    value: Any = Field(..., description="Parameter value")
    type: str = Field(..., description="Parameter type")
    
    @field_validator('value')
    def validate_json_serializable(cls, v):
        """Ensure parameter value is JSON serializable"""
        try:
            import json
            json.dumps(v)
            return v
        except (TypeError, ValueError):
            raise ValueError("Parameter value must be JSON serializable")
    
    class Config:
        use_enum_values = True


class ToolCallResult(BaseModel):
    """Model for tool call results"""
    success: bool = Field(..., description="Whether the tool call succeeded")
    result: Optional[Any] = Field(default=None, description="Tool call result data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    error_type: Optional[str] = Field(default=None, description="Error type classification")
    execution_time: Optional[float] = Field(default=None, description="Execution time in seconds")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('result', 'error')
    def validate_json_serializable(cls, v):
        """Ensure result and error are JSON serializable"""
        if v is not None:
            try:
                import json
                json.dumps(v)
            except (TypeError, ValueError):
                raise ValueError("Result and error must be JSON serializable")
        return v
    
    class Config:
        use_enum_values = True


class ToolCall(BaseModel):
    """Model for tool calls in conversation history"""
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique tool call ID")
    tool_name: str = Field(..., description="Name of the tool being called")
    tool_version: Optional[str] = Field(default=None, description="Version of the tool")
    parameters: List[ToolCallParameter] = Field(default_factory=list, description="Tool call parameters")
    result: Optional[ToolCallResult] = Field(default=None, description="Tool call result")
    status: ToolCallStatus = Field(default=ToolCallStatus.PENDING, description="Tool call status")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="When the tool call was created")
    started_at: Optional[datetime] = Field(default=None, description="When the tool call started executing")
    completed_at: Optional[datetime] = Field(default=None, description="When the tool call completed")
    timeout_seconds: Optional[float] = Field(default=30.0, description="Tool call timeout")
    
    @field_validator('tool_name')
    def validate_tool_name(cls, v):
        """Validate tool name is not empty"""
        if not v or not v.strip():
            raise ValueError("Tool name cannot be empty")
        return v.strip()
    
    class Config:
        use_enum_values = True


class ConversationTurn(BaseModel):
    """Model for individual conversation turns in the JSON structure"""
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="Tool calls made in this turn")
    
    class Config:
        use_enum_values = True


class ChatMessageCreate(BaseModel):
    """Model for creating a new chat message"""
    role: MessageRole
    content: str = Field(..., max_length=10000)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="Tool calls associated with this message")


class ChatMessage(BaseModel):
    """Chat message data model"""
    id: Optional[int] = None
    session_id: str
    role: MessageRole
    content: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    timestamp: Optional[datetime] = None
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="Tool calls associated with this message")
    
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    message_count: int = Field(default=0)
    tool_calls_count: int = Field(default=0, description="Total number of tool calls in this session")
    
    class Config:
        use_enum_values = True


class ChatContext(BaseModel):
    """Model for chat context with recent messages"""
    session_id: str
    messages: List[ChatMessage]
    total_messages: int
    context_window: int = Field(default=5)
    tool_calls_enabled: bool = Field(default=False, description="Whether tool calls are enabled for this context")


class ChatRequest(BaseModel):
    """Model for chat API requests"""
    message: str = Field(..., max_length=10000)
    stream: bool = Field(default=False)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0, le=4000)
    enable_tools: bool = Field(default=True, description="Whether to enable tool calling for this request")


class ChatResponse(BaseModel):
    """Model for chat API responses"""
    message_id: Optional[int] = None
    session_id: str
    content: str
    role: MessageRole = Field(default=MessageRole.ASSISTANT)
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="Tool calls made in this response")
    has_tool_calls: bool = Field(default=False, description="Whether this response contains tool calls")


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
    total_tool_calls: int = Field(default=0, description="Total number of tool calls in this session")


class OpenRouterMessage(BaseModel):
    """Model for OpenRouter API messages"""
    role: str
    content: str


class OpenRouterTool(BaseModel):
    """Model for OpenRouter API tool definitions"""
    type: str = Field(default="function", description="Tool type")
    function: Dict[str, Any] = Field(..., description="Function definition")
    
    class Config:
        use_enum_values = True


class OpenRouterToolCall(BaseModel):
    """Model for OpenRouter API tool calls"""
    id: str = Field(..., description="Tool call ID")
    type: str = Field(default="function", description="Tool call type")
    function: Dict[str, Any] = Field(..., description="Function call details")
    
    class Config:
        use_enum_values = True


class OpenRouterChatRequest(BaseModel):
    """Model for OpenRouter API chat requests"""
    model: str
    messages: List[OpenRouterMessage]
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=1000)
    stream: bool = Field(default=False)
    tools: Optional[List[OpenRouterTool]] = Field(default=None, description="Available tools for this request")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(default=None, description="Tool choice strategy")


class ToolCallEvent(BaseModel):
    """Model for tool call events in streaming responses"""
    event_type: str = Field(..., description="Event type (tool_call_start, tool_call_end, tool_call_error)")
    tool_call_id: str = Field(..., description="Tool call ID")
    tool_name: str = Field(..., description="Tool name")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Event data")
    
    class Config:
        use_enum_values = True


class ToolCallStatistics(BaseModel):
    """Model for tool call statistics"""
    session_id: str = Field(..., description="Session ID")
    total_tool_calls: int = Field(default=0, description="Total tool calls in session")
    successful_tool_calls: int = Field(default=0, description="Successful tool calls")
    failed_tool_calls: int = Field(default=0, description="Failed tool calls")
    average_execution_time: Optional[float] = Field(default=None, description="Average execution time")
    most_used_tool: Optional[str] = Field(default=None, description="Most frequently used tool")
    tools_usage: Dict[str, int] = Field(default_factory=dict, description="Tool usage count by tool name")
    
    class Config:
        use_enum_values = True


class HealthCheck(BaseModel):
    """Model for health check responses"""
    status: str
    timestamp: Optional[datetime] = None
    version: str
    database_connected: bool
    temporal_connected: bool = Field(default=False)
    openrouter_connected: bool = Field(default=False)
    tools_registered: int = Field(default=0, description="Number of registered tools")


class ErrorResponse(BaseModel):
    """Model for error responses"""
    error: str
    message: str
    timestamp: Optional[datetime] = None
    details: Optional[Dict[str, Any]] = None
    tool_call_id: Optional[str] = Field(default=None, description="Tool call ID if error is related to tool calling") 