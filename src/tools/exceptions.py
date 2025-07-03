"""
Custom exceptions for tool calling system
"""
from typing import Optional, Dict, Any


class ToolError(Exception):
    """Base exception for all tool-related errors"""
    
    def __init__(self, message: str, tool_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.tool_name = tool_name
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization"""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "tool_name": self.tool_name,
            "details": self.details
        }


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not found in the registry"""
    
    def __init__(self, tool_name: str):
        super().__init__(f"Tool '{tool_name}' not found in registry", tool_name)


class ToolExecutionError(ToolError):
    """Raised when a tool execution fails"""
    
    def __init__(self, message: str, tool_name: str, original_error: Optional[Exception] = None):
        details = {}
        if original_error:
            details["original_error"] = str(original_error)
            details["original_error_type"] = type(original_error).__name__
        
        super().__init__(f"Tool '{tool_name}' execution failed: {message}", tool_name, details)
        self.original_error = original_error


class ToolValidationError(ToolError):
    """Raised when tool parameter validation fails"""
    
    def __init__(self, message: str, tool_name: str, validation_errors: Optional[Dict[str, Any]] = None):
        details = {"validation_errors": validation_errors or {}}
        super().__init__(f"Tool '{tool_name}' validation failed: {message}", tool_name, details)
        self.validation_errors = validation_errors


class ToolTimeoutError(ToolError):
    """Raised when a tool execution times out"""
    
    def __init__(self, tool_name: str, timeout_seconds: float):
        super().__init__(
            f"Tool '{tool_name}' execution timed out after {timeout_seconds} seconds",
            tool_name,
            {"timeout_seconds": timeout_seconds}
        )
        self.timeout_seconds = timeout_seconds


class ToolConfigurationError(ToolError):
    """Raised when a tool has invalid configuration"""
    
    def __init__(self, message: str, tool_name: str, config_errors: Optional[Dict[str, Any]] = None):
        details = {"config_errors": config_errors or {}}
        super().__init__(f"Tool '{tool_name}' configuration error: {message}", tool_name, details)
        self.config_errors = config_errors


class ToolPermissionError(ToolError):
    """Raised when a tool execution is not permitted"""
    
    def __init__(self, tool_name: str, reason: str):
        super().__init__(
            f"Tool '{tool_name}' execution not permitted: {reason}",
            tool_name,
            {"reason": reason}
        )
        self.reason = reason