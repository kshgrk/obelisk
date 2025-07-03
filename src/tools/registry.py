"""
Enhanced Central tool registry and management system with versioning, 
model capability checking, and access control for Task 7
"""
import importlib
import inspect
import logging
from datetime import datetime
from typing import Dict, List, Optional, Type, Any, Set
from pathlib import Path

from .base import BaseTool
from .schemas import (
    ToolDefinition, ToolRegistration, ToolCall, ToolCallResult, 
    ToolExecutionContext, ToolVersion, ToolPermission, PermissionLevel
)
from .exceptions import (
    ToolNotFoundError, ToolConfigurationError, ToolError, 
    ToolPermissionError, ToolValidationError
)

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Enhanced Central registry for managing and executing tools with versioning and access control"""
    
    def __init__(self):
        self._tools: Dict[str, ToolRegistration] = {}
        self._tool_instances: Dict[str, BaseTool] = {}
        self._initialized = False
        self._capability_manager = None  # Will be set during initialization
        
        # Enhanced Task 7 features
        self._version_registry: Dict[str, Dict[str, ToolRegistration]] = {}  # tool_name -> version -> registration
        self._access_control_enabled = True
        self._default_user_role = "user"
        self._model_capabilities_cache: Dict[str, Dict[str, Any]] = {}
        self._permission_cache: Dict[str, Dict[str, bool]] = {}  # session_id -> tool_name -> allowed
        
    def initialize(self, auto_discover: bool = True, capability_manager=None) -> None:
        """
        Initialize the tool registry with enhanced features
        
        Args:
            auto_discover: Whether to automatically discover tools in implementations directory
            capability_manager: Model capability manager instance for model checking
        """
        if self._initialized:
            logger.warning("Tool registry already initialized")
            return
            
        logger.info("Initializing enhanced tool registry...")
        
        # Set capability manager for model checking
        if capability_manager:
            self._capability_manager = capability_manager
        else:
            # Try to import and create if not provided
            try:
                from ..models.capabilities import ModelCapabilityManager
                self._capability_manager = ModelCapabilityManager()
            except ImportError:
                logger.warning("ModelCapabilityManager not available - model capability checking disabled")
        
        if auto_discover:
            self._discover_tools()
        
        self._initialized = True
        logger.info(f"Enhanced tool registry initialized with {len(self._tools)} tools")
    
    def _discover_tools(self) -> None:
        """Automatically discover and register tools from implementations directory"""
        implementations_path = Path(__file__).parent / "implementations"
        
        if not implementations_path.exists():
            logger.warning(f"Implementations directory not found: {implementations_path}")
            return
        
        discovered_count = 0
        
        # Scan for Python files in implementations directory
        for py_file in implementations_path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
                
            module_name = f"src.tools.implementations.{py_file.stem}"
            
            try:
                module = importlib.import_module(module_name)
                count = self._register_tools_from_module(module)
                discovered_count += count
                logger.info(f"Discovered {count} tools from {py_file.name}")
            except Exception as e:
                logger.error(f"Failed to import tool module {module_name}: {e}")
        
        logger.info(f"Auto-discovery completed: {discovered_count} tools registered")
    
    def _register_tools_from_module(self, module) -> int:
        """Register all tools found in a module"""
        registered_count = 0
        
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BaseTool) and 
                obj is not BaseTool and
                not inspect.isabstract(obj)):
                
                try:
                    tool_instance = obj()
                    self.register_tool(tool_instance)
                    registered_count += 1
                    logger.info(f"Auto-registered tool: {tool_instance.definition.name}")
                except Exception as e:
                    logger.error(f"Failed to register tool {name}: {e}")
        
        return registered_count
    
    def register_tool(self, tool: BaseTool, force_update: bool = False) -> None:
        """
        Register a tool instance with enhanced versioning and validation
        
        Args:
            tool: Tool instance to register
            force_update: Whether to force update if tool exists
            
        Raises:
            ToolConfigurationError: If tool configuration is invalid
        """
        if not isinstance(tool, BaseTool):
            raise ToolConfigurationError("Tool must inherit from BaseTool", tool.__class__.__name__)
        
        definition = tool.definition
        
        # Validate tool definition
        if not definition.name:
            raise ToolConfigurationError("Tool name cannot be empty", tool.__class__.__name__)
        
        # Validate semantic versioning
        try:
            version_info = definition.version_info
        except AttributeError:
            # Create default version info if not provided
            from .schemas import ToolVersion
            version_info = ToolVersion(version=definition.version)
            definition.version_info = version_info
        
        # Check if tool already exists
        if definition.name in self._tools:
            existing_registration = self._tools[definition.name]
            existing_version = existing_registration.definition.version
            
            if not force_update and existing_version == definition.version:
                logger.warning(f"Tool '{definition.name}' version {definition.version} already registered")
                return
            
            logger.info(f"Updating tool '{definition.name}' from v{existing_version} to v{definition.version}")
        
        # Create registration with enhanced features
        registration = ToolRegistration(
            definition=definition,
            implementation_class=f"{tool.__class__.__module__}.{tool.__class__.__name__}",
            enabled=True,
            registered_at=datetime.utcnow()
        )
        
        # Initialize version history
        if definition.name in self._tools:
            # Copy existing version history
            registration.version_history = self._tools[definition.name].version_history.copy()
        
        # Add current version to history
        registration.add_version(version_info)
        
        # Register in main registry
        self._tools[definition.name] = registration
        self._tool_instances[definition.name] = tool
        
        # Register in version registry
        if definition.name not in self._version_registry:
            self._version_registry[definition.name] = {}
        self._version_registry[definition.name][definition.version] = registration
        
        logger.info(f"Registered tool: {definition.name} (v{definition.version})")
    
    def unregister_tool(self, tool_name: str, version: Optional[str] = None) -> None:
        """
        Unregister a tool or specific version
        
        Args:
            tool_name: Name of the tool to unregister
            version: Specific version to unregister (if None, unregisters current)
        """
        if tool_name not in self._tools:
            logger.warning(f"Tool '{tool_name}' not found for unregistration")
            return
        
        if version is None:
            # Unregister current version
            del self._tools[tool_name]
            if tool_name in self._tool_instances:
                del self._tool_instances[tool_name]
            
            # Clear entire version history
            if tool_name in self._version_registry:
                del self._version_registry[tool_name]
            
            logger.info(f"Unregistered tool: {tool_name}")
        else:
            # Unregister specific version
            if (tool_name in self._version_registry and 
                version in self._version_registry[tool_name]):
                del self._version_registry[tool_name][version]
                logger.info(f"Unregistered tool version: {tool_name} v{version}")
            else:
                logger.warning(f"Tool version '{tool_name}' v{version} not found")
        
        # Clear caches
        self._clear_tool_caches(tool_name)
    
    def _clear_tool_caches(self, tool_name: str) -> None:
        """Clear caches for a specific tool"""
        # Clear permission cache
        for session_id in list(self._permission_cache.keys()):
            if tool_name in self._permission_cache[session_id]:
                del self._permission_cache[session_id][tool_name]
        
        # Clear model compatibility cache
        if tool_name in self._tools:
            registration = self._tools[tool_name]
            registration.model_compatibility_cache.clear()
    
    def get_tool(self, tool_name: str, version: Optional[str] = None) -> BaseTool:
        """
        Get a tool instance by name and optionally version
        
        Args:
            tool_name: Name of the tool
            version: Specific version (if None, returns current)
            
        Returns:
            BaseTool: Tool instance
            
        Raises:
            ToolNotFoundError: If tool is not found or disabled
        """
        if version is None:
            # Get current version
            if tool_name not in self._tools:
                raise ToolNotFoundError(tool_name)
            
            registration = self._tools[tool_name]
            if not registration.enabled:
                raise ToolNotFoundError(f"Tool '{tool_name}' is disabled")
            
            return self._tool_instances[tool_name]
        else:
            # Get specific version
            if (tool_name not in self._version_registry or 
                version not in self._version_registry[tool_name]):
                raise ToolNotFoundError(f"Tool '{tool_name}' version {version} not found")
            
            registration = self._version_registry[tool_name][version]
            if not registration.enabled:
                raise ToolNotFoundError(f"Tool '{tool_name}' version {version} is disabled")
            
            # For specific versions, we need to create instance if needed
            # This is a simplified implementation - in production you might want instance caching
            return self._tool_instances[tool_name]  # For now, return current instance
    
    def has_tool(self, tool_name: str, version: Optional[str] = None) -> bool:
        """Check if a tool is registered and enabled"""
        if version is None:
            return (tool_name in self._tools and 
                    self._tools[tool_name].enabled)
        else:
            return (tool_name in self._version_registry and 
                    version in self._version_registry[tool_name] and
                    self._version_registry[tool_name][version].enabled)
    
    def list_tools(self, enabled_only: bool = True, include_versions: bool = False) -> List[str]:
        """
        List all registered tool names with optional version information
        
        Args:
            enabled_only: If True, only return enabled tools
            include_versions: If True, include version information
            
        Returns:
            List[str]: List of tool names (optionally with versions)
        """
        tools = []
        
        if include_versions:
            for tool_name, registrations in self._version_registry.items():
                for version, registration in registrations.items():
                    if not enabled_only or registration.enabled:
                        tools.append(f"{tool_name}@{version}")
        else:
            for name, reg in self._tools.items():
                if not enabled_only or reg.enabled:
                    tools.append(name)
        
        return sorted(tools)
    
    def get_tool_versions(self, tool_name: str) -> List[str]:
        """Get all available versions for a tool"""
        if tool_name not in self._version_registry:
            return []
        
        versions = list(self._version_registry[tool_name].keys())
        return sorted(versions, reverse=True)  # Newest first
    
    async def is_model_compatible(self, tool_name: str, model_id: str) -> bool:
        """
        Check if a tool is compatible with a specific model
        
        Args:
            tool_name: Name of the tool
            model_id: ID of the model to check
            
        Returns:
            bool: True if compatible, False otherwise
        """
        if tool_name not in self._tools:
            return False
        
        registration = self._tools[tool_name]
        
        # Check cache first
        if model_id in registration.model_compatibility_cache:
            return registration.model_compatibility_cache[model_id]
        
        # Get model capabilities
        model_capabilities = await self._get_model_capabilities(model_id)
        if not model_capabilities:
            # If we can't get capabilities, assume compatible
            return True
        
        # Check compatibility
        is_compatible = registration.definition.is_compatible_with_model(model_capabilities)
        
        # Cache result
        registration.model_compatibility_cache[model_id] = is_compatible
        
        return is_compatible
    
    async def _get_model_capabilities(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model capabilities from cache or capability manager"""
        # Check cache first
        if model_id in self._model_capabilities_cache:
            return self._model_capabilities_cache[model_id]
        
        # Get from capability manager
        if self._capability_manager:
            try:
                capability_info = await self._capability_manager.get_model_capability(model_id)
                if capability_info:
                    capabilities = {
                        'supports_tool_calls': capability_info.supports_tool_calls,
                        'context_length': capability_info.context_length,
                        'model_name': capability_info.name
                    }
                    # Cache for future use
                    self._model_capabilities_cache[model_id] = capabilities
                    return capabilities
            except Exception as e:
                logger.warning(f"Failed to get model capabilities for {model_id}: {e}")
        
        return None
    
    def check_tool_permission(self, tool_name: str, session_id: str, user_role: Optional[str] = None, model_id: Optional[str] = None) -> bool:
        """
        Check if a session/user has permission to use a tool
        
        Args:
            tool_name: Name of the tool
            session_id: Session ID
            user_role: User role (defaults to default_user_role)
            model_id: Model ID for model-specific restrictions
            
        Returns:
            bool: True if permitted, False otherwise
        """
        if not self._access_control_enabled:
            return True
        
        if tool_name not in self._tools:
            return False
        
        user_role = user_role or self._default_user_role
        model_id = model_id or "unknown"
        
        # Check cache first
        cache_key = f"{session_id}:{user_role}:{model_id}"
        if (session_id in self._permission_cache and 
            tool_name in self._permission_cache[session_id]):
            cached_result = self._permission_cache[session_id].get(cache_key)
            if cached_result is not None:
                return cached_result
        
        registration = self._tools[tool_name]
        
        # Check basic permission
        has_permission = registration.has_permission(session_id, user_role, model_id)
        
        # Check rate limits
        if has_permission:
            rate_limits = registration.check_rate_limits(session_id)
            if rate_limits.get('hourly_exceeded') or rate_limits.get('session_exceeded'):
                has_permission = False
        
        # Cache result
        if session_id not in self._permission_cache:
            self._permission_cache[session_id] = {}
        self._permission_cache[session_id][cache_key] = has_permission
        
        return has_permission
    
    async def execute_tool(self, tool_call: ToolCall, context: ToolExecutionContext) -> ToolCallResult:
        """
        Execute a tool call with enhanced validation and access control
        
        Args:
            tool_call: Tool call to execute
            context: Execution context
            
        Returns:
            ToolCallResult: Result of the tool execution
            
        Raises:
            ToolNotFoundError: If tool is not found
            ToolPermissionError: If access is denied
        """
        if not self._initialized:
            raise ToolError("Tool registry not initialized")
        
        # Enhanced validation for Task 7
        
        # 1. Check if tool exists
        if not self.has_tool(tool_call.tool_name):
            raise ToolNotFoundError(tool_call.tool_name)
        
        # 2. Check model compatibility
        if not await self.is_model_compatible(tool_call.tool_name, context.ai_model):
            raise ToolPermissionError(
                f"Tool '{tool_call.tool_name}' is not compatible with model '{context.ai_model}'",
                tool_call.tool_name
            )
        
        # 3. Check permissions
        user_role = context.metadata.get('user_role', self._default_user_role)
        if not self.check_tool_permission(tool_call.tool_name, context.session_id, user_role, context.ai_model):
            raise ToolPermissionError(
                f"Access denied for tool '{tool_call.tool_name}' in session '{context.session_id}'",
                tool_call.tool_name
            )
        
        # Get tool instance
        tool = self.get_tool(tool_call.tool_name)
        registration = self._tools[tool_call.tool_name]
        
        # Record usage for rate limiting
        registration.record_usage(context.session_id)
        
        # Update usage statistics
        registration.usage_count += 1
        registration.last_used = datetime.utcnow()
        
        # Execute the tool
        result = await tool.call(tool_call, context)
        
        logger.info(f"Executed tool '{tool_call.tool_name}' with status: {result.status}")
        
        return result
    
    def get_tool_info(self, tool_name: str, include_versions: bool = False) -> Dict[str, Any]:
        """
        Get detailed information about a tool with enhanced metadata
        
        Args:
            tool_name: Name of the tool
            include_versions: Whether to include version history
            
        Returns:
            Dict[str, Any]: Tool information including definition and statistics
        """
        if tool_name not in self._tools:
            raise ToolNotFoundError(tool_name)
        
        registration = self._tools[tool_name]
        tool = self._tool_instances[tool_name]
        definition = registration.definition
        
        info = {
            "name": definition.name,
            "description": definition.description,
            "version": definition.version,
            "parameters": [param.dict() for param in definition.parameters],
            "timeout_seconds": definition.timeout_seconds,
            "implementation_class": registration.implementation_class,
            "enabled": registration.enabled,
            "registered_at": registration.registered_at.isoformat(),
            "last_used": registration.last_used.isoformat() if registration.last_used else None,
            "usage_count": registration.usage_count,
            
            # Enhanced Task 7 fields
            "metadata": definition.metadata.dict(),
            "permissions": definition.permissions.dict(),
            "version_info": definition.version_info.dict(),
            "model_compatibility_cache": dict(registration.model_compatibility_cache),
            "permission_grants": dict(registration.permission_grants),
            "usage_statistics": dict(registration.usage_statistics),
            
            "openrouter_schema": tool.get_openrouter_schema()
        }
        
        if include_versions:
            info["version_history"] = [v.dict() for v in registration.version_history]
            info["available_versions"] = self.get_tool_versions(tool_name)
        
        return info
    
    def get_registry_status(self) -> Dict[str, Any]:
        """Get enhanced registry status and statistics"""
        total_tools = len(self._tools)
        enabled_tools = len([reg for reg in self._tools.values() if reg.enabled])
        total_usage = sum(reg.usage_count for reg in self._tools.values())
        
        # Version statistics
        total_versions = sum(len(versions) for versions in self._version_registry.values())
        
        # Permission statistics
        total_sessions_with_permissions = len(self._permission_cache)
        
        return {
            "initialized": self._initialized,
            "total_tools": total_tools,
            "enabled_tools": enabled_tools,
            "disabled_tools": total_tools - enabled_tools,
            "total_usage_count": total_usage,
            "total_versions": total_versions,
            "access_control_enabled": self._access_control_enabled,
            "sessions_with_cached_permissions": total_sessions_with_permissions,
            "model_capabilities_cached": len(self._model_capabilities_cache),
            "capability_manager_available": self._capability_manager is not None,
            "tools": {name: reg.enabled for name, reg in self._tools.items()},
            "versions_per_tool": {name: len(versions) for name, versions in self._version_registry.items()}
        }
    
    def reload_tools(self) -> None:
        """Reload all tools by rediscovering them"""
        logger.info("Reloading tools...")
        old_count = len(self._tools)
        
        # Clear existing tools but preserve caches temporarily
        old_permission_cache = self._permission_cache.copy()
        old_model_cache = self._model_capabilities_cache.copy()
        
        self._tools.clear()
        self._tool_instances.clear()
        self._version_registry.clear()
        
        # Rediscover tools
        self._discover_tools()
        
        # Restore relevant caches
        self._permission_cache = old_permission_cache
        self._model_capabilities_cache = old_model_cache
        
        new_count = len(self._tools)
        logger.info(f"Reloaded tools: {old_count} -> {new_count}")
    
    # Enhanced Task 7 Methods
    
    def set_access_control(self, enabled: bool) -> None:
        """Enable or disable access control"""
        self._access_control_enabled = enabled
        logger.info(f"Access control {'enabled' if enabled else 'disabled'}")
    
    def set_default_user_role(self, role: str) -> None:
        """Set the default user role for permission checking"""
        self._default_user_role = role
        logger.info(f"Default user role set to: {role}")
    
    async def get_tools_for_model(self, model_id: str) -> List[str]:
        """Get list of tools compatible with a specific model"""
        compatible_tools = []
        
        for tool_name in self._tools:
            if await self.is_model_compatible(tool_name, model_id):
                compatible_tools.append(tool_name)
        
        return compatible_tools
    
    def get_tools_by_permission_level(self, permission_level: PermissionLevel) -> List[str]:
        """Get tools that require a specific permission level"""
        tools = []
        
        for tool_name, registration in self._tools.items():
            if registration.definition.permissions.level == permission_level:
                tools.append(tool_name)
        
        return tools
    
    def get_tools_by_category(self, category: str) -> List[str]:
        """Get tools in a specific category"""
        tools = []
        
        for tool_name, registration in self._tools.items():
            if registration.definition.metadata.category == category:
                tools.append(tool_name)
        
        return tools
    
    def clear_permission_cache(self, session_id: Optional[str] = None) -> None:
        """Clear permission cache for a session or all sessions"""
        if session_id:
            if session_id in self._permission_cache:
                del self._permission_cache[session_id]
                logger.info(f"Cleared permission cache for session: {session_id}")
        else:
            self._permission_cache.clear()
            logger.info("Cleared all permission cache")
    
    def clear_model_compatibility_cache(self) -> None:
        """Clear model compatibility cache"""
        self._model_capabilities_cache.clear()
        for registration in self._tools.values():
            registration.model_compatibility_cache.clear()
        logger.info("Cleared model compatibility cache")


# Global registry instance
tool_registry = ToolRegistry() 