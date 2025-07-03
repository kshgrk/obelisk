"""
Central tool registry and management system
"""
import importlib
import inspect
import logging
from datetime import datetime
from typing import Dict, List, Optional, Type, Any
from pathlib import Path

from .base import BaseTool
from .schemas import ToolDefinition, ToolRegistration, ToolCall, ToolCallResult, ToolExecutionContext
from .exceptions import ToolNotFoundError, ToolConfigurationError, ToolError

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for managing and executing tools"""
    
    def __init__(self):
        self._tools: Dict[str, ToolRegistration] = {}
        self._tool_instances: Dict[str, BaseTool] = {}
        self._initialized = False
        
    def initialize(self, auto_discover: bool = True) -> None:
        """
        Initialize the tool registry
        
        Args:
            auto_discover: Whether to automatically discover tools in implementations directory
        """
        if self._initialized:
            logger.warning("Tool registry already initialized")
            return
            
        logger.info("Initializing tool registry...")
        
        if auto_discover:
            self._discover_tools()
        
        self._initialized = True
        logger.info(f"Tool registry initialized with {len(self._tools)} tools")
    
    def _discover_tools(self) -> None:
        """Automatically discover and register tools from implementations directory"""
        implementations_path = Path(__file__).parent / "implementations"
        
        if not implementations_path.exists():
            logger.warning(f"Implementations directory not found: {implementations_path}")
            return
        
        # Scan for Python files in implementations directory
        for py_file in implementations_path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
                
            module_name = f"src.tools.implementations.{py_file.stem}"
            
            try:
                module = importlib.import_module(module_name)
                self._register_tools_from_module(module)
            except Exception as e:
                logger.error(f"Failed to import tool module {module_name}: {e}")
    
    def _register_tools_from_module(self, module) -> None:
        """Register all tools found in a module"""
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BaseTool) and 
                obj is not BaseTool and
                not inspect.isabstract(obj)):
                
                try:
                    tool_instance = obj()
                    self.register_tool(tool_instance)
                    logger.info(f"Auto-registered tool: {tool_instance.definition.name}")
                except Exception as e:
                    logger.error(f"Failed to register tool {name}: {e}")
    
    def register_tool(self, tool: BaseTool) -> None:
        """
        Register a tool instance
        
        Args:
            tool: Tool instance to register
            
        Raises:
            ToolConfigurationError: If tool configuration is invalid
        """
        if not isinstance(tool, BaseTool):
            raise ToolConfigurationError("Tool must inherit from BaseTool", tool.__class__.__name__)
        
        definition = tool.definition
        
        # Validate tool definition
        if not definition.name:
            raise ToolConfigurationError("Tool name cannot be empty", tool.__class__.__name__)
        
        if definition.name in self._tools:
            logger.warning(f"Tool '{definition.name}' already registered, replacing...")
        
        # Create registration
        registration = ToolRegistration(
            definition=definition,
            implementation_class=f"{tool.__class__.__module__}.{tool.__class__.__name__}",
            enabled=True,
            registered_at=datetime.utcnow()
        )
        
        self._tools[definition.name] = registration
        self._tool_instances[definition.name] = tool
        
        logger.info(f"Registered tool: {definition.name} (v{definition.version})")
    
    def unregister_tool(self, tool_name: str) -> None:
        """
        Unregister a tool
        
        Args:
            tool_name: Name of the tool to unregister
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            if tool_name in self._tool_instances:
                del self._tool_instances[tool_name]
            logger.info(f"Unregistered tool: {tool_name}")
        else:
            logger.warning(f"Tool '{tool_name}' not found for unregistration")
    
    def get_tool(self, tool_name: str) -> BaseTool:
        """
        Get a tool instance by name
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            BaseTool: Tool instance
            
        Raises:
            ToolNotFoundError: If tool is not found or disabled
        """
        if tool_name not in self._tools:
            raise ToolNotFoundError(tool_name)
        
        registration = self._tools[tool_name]
        if not registration.enabled:
            raise ToolNotFoundError(f"Tool '{tool_name}' is disabled")
        
        return self._tool_instances[tool_name]
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is registered and enabled"""
        return (tool_name in self._tools and 
                self._tools[tool_name].enabled)
    
    def list_tools(self, enabled_only: bool = True) -> List[str]:
        """
        List all registered tool names
        
        Args:
            enabled_only: If True, only return enabled tools
            
        Returns:
            List[str]: List of tool names
        """
        if enabled_only:
            return [name for name, reg in self._tools.items() if reg.enabled]
        else:
            return list(self._tools.keys())
    
    def get_tool_definitions(self, enabled_only: bool = True) -> List[ToolDefinition]:
        """
        Get all tool definitions
        
        Args:
            enabled_only: If True, only return enabled tools
            
        Returns:
            List[ToolDefinition]: List of tool definitions
        """
        definitions = []
        for name, registration in self._tools.items():
            if not enabled_only or registration.enabled:
                definitions.append(registration.definition)
        return definitions
    
    def get_openrouter_schemas(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get OpenRouter-compatible tool schemas
        
        Args:
            enabled_only: If True, only return enabled tools
            
        Returns:
            List[Dict[str, Any]]: List of OpenRouter tool schemas
        """
        schemas = []
        for name, registration in self._tools.items():
            if not enabled_only or registration.enabled:
                tool = self._tool_instances[name]
                schemas.append(tool.get_openrouter_schema())
        return schemas
    
    def enable_tool(self, tool_name: str) -> None:
        """Enable a tool"""
        if tool_name in self._tools:
            self._tools[tool_name].enabled = True
            logger.info(f"Enabled tool: {tool_name}")
        else:
            raise ToolNotFoundError(tool_name)
    
    def disable_tool(self, tool_name: str) -> None:
        """Disable a tool"""
        if tool_name in self._tools:
            self._tools[tool_name].enabled = False
            logger.info(f"Disabled tool: {tool_name}")
        else:
            raise ToolNotFoundError(tool_name)
    
    async def execute_tool(self, tool_call: ToolCall, context: ToolExecutionContext) -> ToolCallResult:
        """
        Execute a tool call
        
        Args:
            tool_call: Tool call to execute
            context: Execution context
            
        Returns:
            ToolCallResult: Result of the tool execution
            
        Raises:
            ToolNotFoundError: If tool is not found
        """
        if not self._initialized:
            raise ToolError("Tool registry not initialized")
        
        tool = self.get_tool(tool_call.tool_name)
        
        # Update usage statistics
        registration = self._tools[tool_call.tool_name]
        registration.usage_count += 1
        registration.last_used = datetime.utcnow()
        
        # Execute the tool
        result = await tool.call(tool_call, context)
        
        logger.info(f"Executed tool '{tool_call.tool_name}' with status: {result.status}")
        
        return result
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a tool
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Dict[str, Any]: Tool information including definition and statistics
        """
        if tool_name not in self._tools:
            raise ToolNotFoundError(tool_name)
        
        registration = self._tools[tool_name]
        tool = self._tool_instances[tool_name]
        
        return {
            "name": registration.definition.name,
            "description": registration.definition.description,
            "version": registration.definition.version,
            "parameters": [param.dict() for param in registration.definition.parameters],
            "timeout_seconds": registration.definition.timeout_seconds,
            "implementation_class": registration.implementation_class,
            "enabled": registration.enabled,
            "registered_at": registration.registered_at.isoformat(),
            "last_used": registration.last_used.isoformat() if registration.last_used else None,
            "usage_count": registration.usage_count,
            "openrouter_schema": tool.get_openrouter_schema()
        }
    
    def get_registry_status(self) -> Dict[str, Any]:
        """Get overall registry status and statistics"""
        total_tools = len(self._tools)
        enabled_tools = len([reg for reg in self._tools.values() if reg.enabled])
        total_usage = sum(reg.usage_count for reg in self._tools.values())
        
        return {
            "initialized": self._initialized,
            "total_tools": total_tools,
            "enabled_tools": enabled_tools,
            "disabled_tools": total_tools - enabled_tools,
            "total_usage_count": total_usage,
            "tools": {name: reg.enabled for name, reg in self._tools.items()}
        }
    
    def reload_tools(self) -> None:
        """Reload all tools by rediscovering them"""
        logger.info("Reloading tools...")
        old_count = len(self._tools)
        
        # Clear existing tools
        self._tools.clear()
        self._tool_instances.clear()
        
        # Rediscover tools
        self._discover_tools()
        
        new_count = len(self._tools)
        logger.info(f"Reloaded tools: {old_count} -> {new_count}")


# Global registry instance
tool_registry = ToolRegistry() 