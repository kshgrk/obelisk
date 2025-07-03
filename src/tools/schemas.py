"""
Tool parameter schemas using Pydantic for validation and serialization
"""
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class ParameterType(str, Enum):
    """Supported parameter types for tools"""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ToolParameter(BaseModel):
    """Schema for a single tool parameter"""
    name: str = Field(..., description="Parameter name")
    type: ParameterType = Field(..., description="Parameter type")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=False, description="Whether parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value if not required")
    enum: Optional[List[Any]] = Field(default=None, description="Allowed values for the parameter")
    min_value: Optional[Union[int, float]] = Field(default=None, description="Minimum value for numbers")
    max_value: Optional[Union[int, float]] = Field(default=None, description="Maximum value for numbers")
    min_length: Optional[int] = Field(default=None, description="Minimum length for strings/arrays")
    max_length: Optional[int] = Field(default=None, description="Maximum length for strings/arrays")
    pattern: Optional[str] = Field(default=None, description="Regex pattern for string validation")
    
    @field_validator('default')
    def validate_default_type(cls, v, info):
        """Validate that default value matches the parameter type"""
        if v is None:
            return v
        
        # Get the type from the data being validated
        param_type = info.data.get('type') if hasattr(info, 'data') else None
        if param_type is None:
            return v  # Skip validation if type not available yet
            
        if param_type == ParameterType.STRING and not isinstance(v, str):
            raise ValueError("Default value must be a string for string parameters")
        elif param_type == ParameterType.INTEGER and not isinstance(v, int):
            raise ValueError("Default value must be an integer for integer parameters")
        elif param_type == ParameterType.NUMBER and not isinstance(v, (int, float)):
            raise ValueError("Default value must be a number for number parameters")
        elif param_type == ParameterType.BOOLEAN and not isinstance(v, bool):
            raise ValueError("Default value must be a boolean for boolean parameters")
        elif param_type == ParameterType.ARRAY and not isinstance(v, list):
            raise ValueError("Default value must be a list for array parameters")
        elif param_type == ParameterType.OBJECT and not isinstance(v, dict):
            raise ValueError("Default value must be a dict for object parameters")
        
        return v
    
    def to_openrouter_schema(self) -> Dict[str, Any]:
        """Convert to OpenRouter tool parameter schema"""
        schema: Dict[str, Any] = {
            "type": self.type.value,
            "description": self.description
        }
        
        if self.enum:
            schema["enum"] = self.enum
        if self.min_value is not None:
            schema["minimum"] = self.min_value
        if self.max_value is not None:
            schema["maximum"] = self.max_value
        if self.min_length is not None:
            schema["minLength"] = self.min_length
        if self.max_length is not None:
            schema["maxLength"] = self.max_length
        if self.pattern:
            schema["pattern"] = self.pattern
        
        return schema


class ToolDefinition(BaseModel):
    """Schema for tool definition that can be sent to OpenRouter"""
    name: str = Field(..., description="Tool name (must be valid identifier)")
    description: str = Field(..., description="Tool description")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")
    version: str = Field(default="1.0.0", description="Tool version")
    timeout_seconds: float = Field(default=30.0, description="Tool execution timeout")
    
    @field_validator('name')
    def validate_name(cls, v):
        """Validate tool name is a valid identifier"""
        if not v.isidentifier():
            raise ValueError("Tool name must be a valid Python identifier")
        return v
    
    def get_required_parameters(self) -> List[str]:
        """Get list of required parameter names"""
        return [param.name for param in self.parameters if param.required]
    
    def get_parameter_by_name(self, name: str) -> Optional[ToolParameter]:
        """Get parameter by name"""
        for param in self.parameters:
            if param.name == name:
                return param
        return None
    
    def to_openrouter_schema(self) -> Dict[str, Any]:
        """Convert to OpenRouter tool schema format"""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_openrouter_schema()
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


class ToolCallStatus(str, Enum):
    """Tool call execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ToolCall(BaseModel):
    """Schema for a tool call request"""
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique tool call ID")
    tool_name: str = Field(..., description="Name of the tool to call")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the tool call was created")
    status: ToolCallStatus = Field(default=ToolCallStatus.PENDING, description="Tool call status")
    timeout_seconds: Optional[float] = Field(default=None, description="Override tool timeout")
    
    class Config:
        use_enum_values = True


class ToolCallResult(BaseModel):
    """Schema for tool call result"""
    call_id: str = Field(..., description="ID of the tool call this is a result for")
    tool_name: str = Field(..., description="Name of the tool that was called")
    status: ToolCallStatus = Field(..., description="Final status of the tool call")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Tool execution result (JSON)")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Error information if failed")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the result was generated")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        use_enum_values = True
    
    @field_validator('result', 'error')
    def validate_json_serializable(cls, v):
        """Ensure result and error are JSON serializable"""
        if v is None:
            return v
        
        try:
            import json
            json.dumps(v)
            return v
        except (TypeError, ValueError) as e:
            raise ValueError(f"Value must be JSON serializable: {e}")
    
    def is_success(self) -> bool:
        """Check if the tool call was successful"""
        return self.status == ToolCallStatus.COMPLETED and self.error is None
    
    def is_error(self) -> bool:
        """Check if the tool call resulted in an error"""
        return self.status in [ToolCallStatus.FAILED, ToolCallStatus.TIMEOUT] or self.error is not None


class ToolExecutionContext(BaseModel):
    """Context information for tool execution"""
    session_id: str = Field(..., description="Chat session ID")
    user_id: Optional[str] = Field(default=None, description="User ID if available")
    ai_model: str = Field(..., description="AI model that requested the tool call")
    conversation_turn: int = Field(..., description="Conversation turn number")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")
    
    model_config = {"protected_namespaces": ()}


class ToolRegistration(BaseModel):
    """Schema for tool registration in the registry"""
    definition: ToolDefinition = Field(..., description="Tool definition")
    implementation_class: str = Field(..., description="Full class path for the tool implementation")
    enabled: bool = Field(default=True, description="Whether the tool is enabled")
    registered_at: datetime = Field(default_factory=datetime.utcnow, description="When the tool was registered")
    last_used: Optional[datetime] = Field(default=None, description="When the tool was last used")
    usage_count: int = Field(default=0, description="Number of times tool has been used")
    
    class Config:
        use_enum_values = True 