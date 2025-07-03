"""
Models package for Obelisk - Chat and capability management
"""

# Chat models
from .chat import (
    # Core models
    ChatMessage,
    ChatSession,
    ChatMessageCreate,
    ChatSessionCreate,
    ChatRequest,
    ChatResponse,
    ChatContext,
    ConversationTurn,
    
    # Tool calling models
    ToolCall,
    ToolCallParameter,
    ToolCallResult,
    ToolCallStatistics,
    ToolCallEvent,
    
    # Enums
    MessageRole,
    SessionStatus,
    ToolCallStatus,
    
    # API models
    OpenRouterMessage,
    OpenRouterTool,
    OpenRouterToolCall,
    OpenRouterChatRequest,
    
    # Response models
    SessionListResponse,
    SessionHistoryResponse,
    HealthCheck,
    ErrorResponse,
)

# Capability detection
from .capabilities import (
    ModelCapability,
    ModelCapabilityManager,
    get_capability_manager,
    supports_tool_calls,
    get_tool_capable_models,
    refresh_model_capabilities,
    validate_model_for_tools,
)

__all__ = [
    # Chat models
    "ChatMessage",
    "ChatSession", 
    "ChatMessageCreate",
    "ChatSessionCreate",
    "ChatRequest",
    "ChatResponse",
    "ChatContext",
    "ConversationTurn",
    
    # Tool calling models
    "ToolCall",
    "ToolCallParameter", 
    "ToolCallResult",
    "ToolCallStatistics",
    "ToolCallEvent",
    
    # Enums
    "MessageRole",
    "SessionStatus",
    "ToolCallStatus",
    
    # API models
    "OpenRouterMessage",
    "OpenRouterTool",
    "OpenRouterToolCall",
    "OpenRouterChatRequest",
    
    # Response models
    "SessionListResponse",
    "SessionHistoryResponse",
    "HealthCheck",
    "ErrorResponse",
    
    # Capability detection
    "ModelCapability",
    "ModelCapabilityManager",
    "get_capability_manager",
    "supports_tool_calls",
    "get_tool_capable_models", 
    "refresh_model_capabilities",
    "validate_model_for_tools",
]
