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

# Capability detection - lazy import to avoid circular imports
def _import_capabilities():
    """Lazy import of capabilities to avoid circular import issues"""
    from .capabilities import (
        ModelCapability,
        ModelCapabilityManager,
        get_capability_manager,
        supports_tool_calls,
        get_tool_capable_models,
        refresh_model_capabilities,
        validate_model_for_tools,
    )
    return {
        'ModelCapability': ModelCapability,
        'ModelCapabilityManager': ModelCapabilityManager,
        'get_capability_manager': get_capability_manager,
        'supports_tool_calls': supports_tool_calls,
        'get_tool_capable_models': get_tool_capable_models,
        'refresh_model_capabilities': refresh_model_capabilities,
        'validate_model_for_tools': validate_model_for_tools,
    }

# Make capabilities available via __getattr__ for lazy loading
def __getattr__(name):
    if name in ['ModelCapability', 'ModelCapabilityManager', 'get_capability_manager',
                'supports_tool_calls', 'get_tool_capable_models', 'refresh_model_capabilities',
                'validate_model_for_tools']:
        capabilities = _import_capabilities()
        return capabilities[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

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
    
    # Capability detection - available via lazy loading
    "ModelCapability",
    "ModelCapabilityManager",
    "get_capability_manager",
    "supports_tool_calls",
    "get_tool_capable_models", 
    "refresh_model_capabilities",
    "validate_model_for_tools",
]
