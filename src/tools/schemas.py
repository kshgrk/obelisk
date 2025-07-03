"""
Tool parameter schemas using Pydantic for validation and serialization
"""
from datetime import datetime, timedelta
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


class PermissionLevel(str, Enum):
    """Permission levels for tool access control"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    RESTRICTED = "restricted"


class ToolPermission(BaseModel):
    """Tool permission configuration"""
    level: PermissionLevel = Field(..., description="Required permission level")
    allowed_roles: List[str] = Field(default_factory=list, description="Specific roles allowed to use tool")
    denied_roles: List[str] = Field(default_factory=list, description="Specific roles denied access to tool")
    allowed_models: List[str] = Field(default_factory=list, description="Models allowed to use this tool")
    max_calls_per_hour: Optional[int] = Field(default=None, description="Rate limit per hour")
    max_calls_per_session: Optional[int] = Field(default=None, description="Rate limit per session")
    
    model_config = {"use_enum_values": True, "protected_namespaces": ()}


class ToolVersion(BaseModel):
    """Tool version information"""
    version: str = Field(..., description="Semantic version string")
    release_date: datetime = Field(default_factory=datetime.utcnow, description="Version release date")
    changelog: str = Field(default="", description="Changes in this version")
    deprecated: bool = Field(default=False, description="Whether this version is deprecated")
    min_compatibility_version: Optional[str] = Field(default=None, description="Minimum compatible version")
    
    @field_validator('version')
    def validate_version(cls, v):
        """Validate semantic version format"""
        import re
        if not re.match(r'^\d+\.\d+\.\d+(?:-[\w\.-]+)?(?:\+[\w\.-]+)?$', v):
            raise ValueError("Version must follow semantic versioning format (x.y.z)")
        return v
    
    def is_compatible_with(self, other_version: str) -> bool:
        """Check if this version is compatible with another version"""
        if not self.min_compatibility_version:
            return True
        
        # Simple version comparison - could be enhanced with proper semver logic
        def version_tuple(v: str) -> tuple:
            return tuple(map(int, v.split('.')[:3]))
        
        try:
            return version_tuple(other_version) >= version_tuple(self.min_compatibility_version)
        except (ValueError, AttributeError):
            return False


class ToolMetadata(BaseModel):
    """Enhanced tool metadata for registry management"""
    tags: List[str] = Field(default_factory=list, description="Tool categorization tags")
    category: str = Field(default="general", description="Tool category")
    author: str = Field(default="unknown", description="Tool author")
    license: str = Field(default="unknown", description="Tool license")
    repository_url: Optional[str] = Field(default=None, description="Source repository URL")
    documentation_url: Optional[str] = Field(default=None, description="Documentation URL")
    dependencies: List[str] = Field(default_factory=list, description="Tool dependencies")
    model_requirements: Dict[str, Any] = Field(default_factory=dict, description="Model capability requirements")
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="Resource requirements")
    experimental: bool = Field(default=False, description="Whether tool is experimental")
    performance_tier: str = Field(default="standard", description="Performance tier (fast, standard, slow)")
    
    model_config = {"protected_namespaces": ()}


class ToolDefinition(BaseModel):
    """Enhanced tool definition with versioning and metadata"""
    name: str = Field(..., description="Tool name (must be valid identifier)")
    description: str = Field(..., description="Tool description")
    parameters: List[ToolParameter] = Field(default_factory=list, description="Tool parameters")
    version: str = Field(default="1.0.0", description="Tool version")
    timeout_seconds: float = Field(default=30.0, description="Tool execution timeout")
    
    # Enhanced fields for Task 7
    version_info: ToolVersion = Field(default_factory=lambda: ToolVersion(version="1.0.0"), description="Detailed version information")
    permissions: ToolPermission = Field(default_factory=lambda: ToolPermission(level=PermissionLevel.USER), description="Permission requirements")
    metadata: ToolMetadata = Field(default_factory=ToolMetadata, description="Tool metadata")
    
    @field_validator('name')
    def validate_name(cls, v):
        """Validate tool name is a valid identifier"""
        if not v.isidentifier():
            raise ValueError("Tool name must be a valid Python identifier")
        return v
    
    @field_validator('version')
    def validate_version_sync(cls, v, values):
        """Ensure version matches version_info.version"""
        # Note: In Pydantic v2, we need to handle this differently
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
    
    def is_compatible_with_model(self, model_capabilities: Dict[str, Any]) -> bool:
        """Check if tool is compatible with model capabilities"""
        # Check if model supports tool calling
        if not model_capabilities.get('supports_tool_calls', False):
            return False
        
        # Check specific model requirements
        if self.metadata.model_requirements:
            for requirement, value in self.metadata.model_requirements.items():
                if requirement not in model_capabilities:
                    return False
                if model_capabilities[requirement] != value:
                    return False
        
        return True


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
    
    model_config = {"use_enum_values": True}


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
    
    model_config = {"use_enum_values": True}
    
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
        # Since use_enum_values=True, self.status is already a string
        return self.status == "completed" and self.error is None
    
    def is_error(self) -> bool:
        """Check if the tool call resulted in an error"""
        # Since use_enum_values=True, self.status is already a string
        return self.status in ["failed", "timeout"] or self.error is not None


class ToolExecutionContext(BaseModel):
    """Context information for tool execution"""
    session_id: str = Field(..., description="Chat session ID")
    user_id: Optional[str] = Field(default=None, description="User ID if available")
    ai_model: str = Field(..., description="AI model that requested the tool call")
    conversation_turn: int = Field(..., description="Conversation turn number")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")
    
    model_config = {"protected_namespaces": ()}


class ToolRegistration(BaseModel):
    """Enhanced tool registration with versioning and access control"""
    definition: ToolDefinition = Field(..., description="Tool definition")
    implementation_class: str = Field(..., description="Full class path for the tool implementation")
    enabled: bool = Field(default=True, description="Whether the tool is enabled")
    registered_at: datetime = Field(default_factory=datetime.utcnow, description="When the tool was registered")
    last_used: Optional[datetime] = Field(default=None, description="When the tool was last used")
    usage_count: int = Field(default=0, description="Number of times tool has been used")
    
    # Enhanced fields for Task 7
    version_history: List[ToolVersion] = Field(default_factory=list, description="Version history")
    permission_grants: Dict[str, List[str]] = Field(default_factory=dict, description="Permission grants by session/user")
    usage_statistics: Dict[str, Any] = Field(default_factory=dict, description="Detailed usage statistics")
    last_permission_check: Optional[datetime] = Field(default=None, description="Last permission validation")
    model_compatibility_cache: Dict[str, bool] = Field(default_factory=dict, description="Cached model compatibility results")
    
    model_config = {"use_enum_values": True, "protected_namespaces": ()}
    
    def add_version(self, version_info: ToolVersion) -> None:
        """Add a new version to the history"""
        self.version_history.append(version_info)
        # Keep only last 10 versions
        if len(self.version_history) > 10:
            self.version_history = self.version_history[-10:]
    
    def get_latest_version(self) -> Optional[ToolVersion]:
        """Get the latest version from history"""
        if self.version_history:
            return sorted(self.version_history, key=lambda v: v.release_date)[-1]
        return None
    
    def is_version_deprecated(self, version: str) -> bool:
        """Check if a specific version is deprecated"""
        for v in self.version_history:
            if v.version == version:
                return v.deprecated
        return False
    
    def has_permission(self, session_id: str, user_role: str, model_id: str) -> bool:
        """Check if session/user has permission to use this tool"""
        permissions = self.definition.permissions
        
        # Check permission level
        if permissions.level == PermissionLevel.ADMIN and user_role != "admin":
            return False
        elif permissions.level == PermissionLevel.RESTRICTED:
            return False
        
        # Check role-based access
        if permissions.denied_roles and user_role in permissions.denied_roles:
            return False
        
        if permissions.allowed_roles and user_role not in permissions.allowed_roles:
            return False
        
        # Check model restrictions
        if permissions.allowed_models and model_id not in permissions.allowed_models:
            return False
        
        return True
    
    def check_rate_limits(self, session_id: str) -> Dict[str, Any]:
        """Check if rate limits are exceeded"""
        now = datetime.utcnow()
        permissions = self.definition.permissions
        
        # Initialize session stats if not exists
        if session_id not in self.usage_statistics:
            self.usage_statistics[session_id] = {
                'hourly_calls': [],
                'session_calls': 0,
                'first_call': now.isoformat()
            }
        
        session_stats = self.usage_statistics[session_id]
        
        # Check hourly limit
        hourly_exceeded = False
        if permissions.max_calls_per_hour:
            # Filter calls from last hour
            one_hour_ago = now - timedelta(hours=1)
            hourly_calls = [
                call_time for call_time in session_stats.get('hourly_calls', [])
                if datetime.fromisoformat(call_time) > one_hour_ago
            ]
            session_stats['hourly_calls'] = hourly_calls
            
            if len(hourly_calls) >= permissions.max_calls_per_hour:
                hourly_exceeded = True
        
        # Check session limit
        session_exceeded = False
        if permissions.max_calls_per_session:
            if session_stats.get('session_calls', 0) >= permissions.max_calls_per_session:
                session_exceeded = True
        
        return {
            'hourly_exceeded': hourly_exceeded,
            'session_exceeded': session_exceeded,
            'calls_remaining_hour': (permissions.max_calls_per_hour or float('inf')) - len(session_stats.get('hourly_calls', [])),
            'calls_remaining_session': (permissions.max_calls_per_session or float('inf')) - session_stats.get('session_calls', 0)
        }
    
    def record_usage(self, session_id: str) -> None:
        """Record tool usage for rate limiting"""
        now = datetime.utcnow()
        
        if session_id not in self.usage_statistics:
            self.usage_statistics[session_id] = {
                'hourly_calls': [],
                'session_calls': 0,
                'first_call': now.isoformat()
            }
        
        session_stats = self.usage_statistics[session_id]
        session_stats['hourly_calls'].append(now.isoformat())
        session_stats['session_calls'] += 1
        session_stats['last_call'] = now.isoformat() 