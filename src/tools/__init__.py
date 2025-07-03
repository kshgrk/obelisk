"""
Tools package for the Obelisk tool calling system

This package provides a comprehensive framework for creating, registering, and executing
tools within the Obelisk chat platform. It includes support for parameter validation,
metrics tracking, error handling, and integration with OpenRouter API.

Enhanced Base Framework (Task 5):
- ToolMetrics: Performance tracking and analytics
- ToolExecutor: Advanced execution workflows with retry logic and parallel processing  
- BaseTool: Enhanced with hooks, validation, and metrics
- Helper functions for creating simple tools and middleware
"""

# Core base classes and utilities
from .base import (
    BaseTool, 
    ToolResult, 
    ToolMetrics, 
    ToolExecutor,
    get_tool_executor,
    create_simple_tool,
    create_error_middleware,
    create_logging_processor
)

# Tool registry
from .registry import tool_registry, ToolRegistry

# Schemas and data models
from .schemas import (
    ToolDefinition,
    ToolParameter, 
    ParameterType,
    ToolCall,
    ToolCallResult,
    ToolCallStatus,
    ToolExecutionContext,
    ToolRegistration
)

# Exception classes
from .exceptions import (
    ToolError,
    ToolNotFoundError,
    ToolValidationError,
    ToolExecutionError,
    ToolTimeoutError,
    ToolConfigurationError,
    ToolPermissionError
)

__all__ = [
    # Base framework classes
    'BaseTool',
    'ToolResult', 
    'ToolMetrics',
    'ToolExecutor',
    'get_tool_executor',
    
    # Helper functions
    'create_simple_tool',
    'create_error_middleware', 
    'create_logging_processor',
    
    # Registry
    'tool_registry',
    'ToolRegistry',
    
    # Schemas
    'ToolDefinition',
    'ToolParameter',
    'ParameterType', 
    'ToolCall',
    'ToolCallResult',
    'ToolCallStatus',
    'ToolExecutionContext',
    'ToolRegistration',
    
    # Exceptions
    'ToolError',
    'ToolNotFoundError',
    'ToolValidationError',
    'ToolExecutionError', 
    'ToolTimeoutError',
    'ToolConfigurationError',
    'ToolPermissionError'
]

# Package metadata
__version__ = "1.0.0"
__description__ = "Comprehensive tool calling framework for Obelisk"
__author__ = "Obelisk Development Team" 