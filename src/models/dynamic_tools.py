"""
Dynamic Tool Registration System
Handles model changes mid-session and manages tool availability
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.models.capabilities import ModelCapabilityManager, ModelCapability
from src.tools.registry import ToolRegistry, tool_registry
from src.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolAvailabilityStatus(Enum):
    """Status of tool availability for a model"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    DEPRECATED = "deprecated"


@dataclass
class SessionToolState:
    """Tracks tool state for a specific session"""
    session_id: str
    current_model: str
    available_tools: Set[str] = field(default_factory=set)
    registered_tools: Dict[str, Any] = field(default_factory=dict)
    last_model_change: Optional[datetime] = None
    tool_cache_expiry: Optional[datetime] = None
    model_switch_count: int = 0
    
    def __post_init__(self):
        if self.last_model_change is None:
            self.last_model_change = datetime.utcnow()
        if self.tool_cache_expiry is None:
            self.tool_cache_expiry = datetime.utcnow() + timedelta(hours=1)


@dataclass
class ModelChangeEvent:
    """Event data for model changes"""
    session_id: str
    old_model: str
    new_model: str
    timestamp: datetime
    tools_before: Set[str]
    tools_after: Set[str]
    tools_added: Set[str]
    tools_removed: Set[str]
    
    @classmethod
    def create(cls, session_id: str, old_model: str, new_model: str, 
               tools_before: Set[str], tools_after: Set[str]) -> 'ModelChangeEvent':
        """Create a model change event with calculated differences"""
        timestamp = datetime.utcnow()
        tools_added = tools_after - tools_before
        tools_removed = tools_before - tools_after
        
        return cls(
            session_id=session_id,
            old_model=old_model,
            new_model=new_model,
            timestamp=timestamp,
            tools_before=tools_before,
            tools_after=tools_after,
            tools_added=tools_added,
            tools_removed=tools_removed
        )


class DynamicToolRegistry:
    """Manages dynamic tool registration and model switching"""
    
    def __init__(self, capability_manager: Optional[ModelCapabilityManager] = None,
                 tool_registry_instance: Optional[ToolRegistry] = None):
        self.capability_manager = capability_manager
        self.tool_registry = tool_registry_instance or tool_registry
        self.session_states: Dict[str, SessionToolState] = {}
        self.model_change_history: List[ModelChangeEvent] = []
        self._cache_ttl = timedelta(hours=1)
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize the dynamic tool registry"""
        if self.capability_manager is None:
            from src.models.capabilities import get_capability_manager
            self.capability_manager = await get_capability_manager()
        
        await self.capability_manager.initialize()
        
        # Initialize the tool registry if not already initialized
        if not self.tool_registry._initialized:
            self.tool_registry.initialize(auto_discover=True, capability_manager=self.capability_manager)
        
        logger.info(f"Dynamic tool registry initialized with {len(self.tool_registry.list_tools())} tools")
    
    async def register_session(self, session_id: str, model_id: str) -> SessionToolState:
        """Register a new session with initial model"""
        async with self._lock:
            # Get available tools for the model
            available_tools = await self._get_available_tools_for_model(model_id)
            
            # Create session state
            session_state = SessionToolState(
                session_id=session_id,
                current_model=model_id,
                available_tools=set(available_tools.keys()),
                registered_tools=available_tools
            )
            
            self.session_states[session_id] = session_state
            
            logger.info(f"Registered session {session_id} with model {model_id}, "
                       f"available tools: {list(available_tools.keys())}")
            
            return session_state
    
    async def switch_model(self, session_id: str, new_model_id: str) -> ModelChangeEvent:
        """Switch model for a session and update tool availability"""
        async with self._lock:
            if session_id not in self.session_states:
                raise ValueError(f"Session {session_id} not registered")
            
            session_state = self.session_states[session_id]
            old_model = session_state.current_model
            tools_before = session_state.available_tools.copy()
            
            # Get tools for new model
            new_available_tools = await self._get_available_tools_for_model(new_model_id)
            tools_after = set(new_available_tools.keys())
            
            # Create change event
            change_event = ModelChangeEvent.create(
                session_id=session_id,
                old_model=old_model,
                new_model=new_model_id,
                tools_before=tools_before,
                tools_after=tools_after
            )
            
            # Update session state
            session_state.current_model = new_model_id
            session_state.available_tools = tools_after
            session_state.registered_tools = new_available_tools
            session_state.last_model_change = change_event.timestamp
            session_state.model_switch_count += 1
            session_state.tool_cache_expiry = datetime.utcnow() + self._cache_ttl
            
            # Record change event
            self.model_change_history.append(change_event)
            
            logger.info(f"Model switch for session {session_id}: {old_model} → {new_model_id}")
            logger.info(f"Tools added: {change_event.tools_added}")
            logger.info(f"Tools removed: {change_event.tools_removed}")
            
            return change_event
    
    async def get_available_tools(self, session_id: str, 
                                 refresh_cache: bool = False) -> Dict[str, Any]:
        """Get available tools for a session"""
        if session_id not in self.session_states:
            raise ValueError(f"Session {session_id} not registered")
        
        session_state = self.session_states[session_id]
        
        # Check if cache needs refresh
        if (refresh_cache or 
            (session_state.tool_cache_expiry is not None and 
             datetime.utcnow() > session_state.tool_cache_expiry)):
            
            async with self._lock:
                # Refresh tools for current model
                new_tools = await self._get_available_tools_for_model(
                    session_state.current_model
                )
                session_state.registered_tools = new_tools
                session_state.available_tools = set(new_tools.keys())
                session_state.tool_cache_expiry = datetime.utcnow() + self._cache_ttl
                
                logger.debug(f"Refreshed tool cache for session {session_id}")
        
        return session_state.registered_tools
    
    async def validate_tool_call(self, session_id: str, tool_name: str) -> Tuple[bool, str]:
        """Validate if a tool call is available for the session"""
        if session_id not in self.session_states:
            return False, f"Session {session_id} not registered"
        
        session_state = self.session_states[session_id]
        
        if tool_name not in session_state.available_tools:
            # Check if tool exists but is unavailable for current model
            all_tool_names = self.tool_registry.list_tools(enabled_only=False)
            if tool_name in all_tool_names:
                return False, f"Tool '{tool_name}' not available for model '{session_state.current_model}'"
            else:
                return False, f"Tool '{tool_name}' does not exist"
        
        return True, "Tool available"
    
    async def get_tool_compatibility_matrix(self) -> Dict[str, Dict[str, ToolAvailabilityStatus]]:
        """Get compatibility matrix of tools vs models"""
        if self.capability_manager is None:
            return {}
            
        all_models = await self.capability_manager.get_all_models()
        all_tool_names = self.tool_registry.list_tools(enabled_only=False)
        
        matrix = {}
        
        for model in all_models:
            model_tools = {}
            
            if model.supports_tool_calls:
                # For tool-capable models, all tools are available
                for tool_name in all_tool_names:
                    model_tools[tool_name] = ToolAvailabilityStatus.AVAILABLE
            else:
                # For non-tool models, all tools are unavailable
                for tool_name in all_tool_names:
                    model_tools[tool_name] = ToolAvailabilityStatus.UNAVAILABLE
            
            matrix[model.model_id] = model_tools
        
        return matrix
    
    async def get_session_state(self, session_id: str) -> Optional[SessionToolState]:
        """Get session tool state"""
        return self.session_states.get(session_id)
    
    async def get_model_change_history(self, session_id: Optional[str] = None) -> List[ModelChangeEvent]:
        """Get model change history, optionally filtered by session"""
        if session_id:
            return [event for event in self.model_change_history 
                   if event.session_id == session_id]
        return self.model_change_history.copy()
    
    async def cleanup_session(self, session_id: str) -> bool:
        """Clean up session data"""
        async with self._lock:
            if session_id in self.session_states:
                del self.session_states[session_id]
                logger.info(f"Cleaned up session {session_id}")
                return True
            return False
    
    async def get_fallback_models(self, current_model: str, 
                                 required_tools: Set[str]) -> List[ModelCapability]:
        """Get fallback models that support the required tools"""
        if self.capability_manager is None:
            return []
            
        tool_capable_models = await self.capability_manager.get_tool_capable_models()
        
        # Filter out current model and return alternatives
        fallback_models = [
            model for model in tool_capable_models 
            if model.model_id != current_model
        ]
        
        # Sort by context length (prefer larger context)
        fallback_models.sort(key=lambda x: x.context_length, reverse=True)
        
        return fallback_models
    
    async def suggest_model_switch(self, session_id: str, 
                                  required_tools: Set[str]) -> Optional[ModelCapability]:
        """Suggest a model switch if current model doesn't support required tools"""
        if session_id not in self.session_states:
            return None
        
        session_state = self.session_states[session_id]
        available_tools = session_state.available_tools
        
        # Check if all required tools are available
        if required_tools.issubset(available_tools):
            return None  # No switch needed
        
        # Find missing tools
        missing_tools = required_tools - available_tools
        
        # Get fallback models that support tools
        fallback_models = await self.get_fallback_models(
            session_state.current_model, required_tools
        )
        
        if fallback_models:
            logger.info(f"Suggesting model switch for session {session_id}: "
                       f"missing tools {missing_tools}, suggested model: {fallback_models[0].model_id}")
            return fallback_models[0]
        
        return None
    
    async def _get_available_tools_for_model(self, model_id: str) -> Dict[str, Any]:
        """Get available tools for a specific model"""
        if self.capability_manager is None:
            return {}
            
        # Check if model supports tool calling
        supports_tools = await self.capability_manager.supports_tool_calls(model_id)
        
        if not supports_tools:
            return {}
        
        # Get all available tool names
        all_tool_names = self.tool_registry.list_tools(enabled_only=True)
        
        # For now, all tools are available for all tool-capable models
        # In the future, this could be more sophisticated with tool-specific requirements
        available_tools = {}
        for tool_name in all_tool_names:
            try:
                tool_instance = self.tool_registry.get_tool(tool_name)
                available_tools[tool_name] = {
                    "name": tool_name,
                    "description": tool_instance.definition.description,
                    "parameters": tool_instance.get_openrouter_schema(),
                    "instance": tool_instance
                }
            except Exception as e:
                logger.warning(f"Failed to get tool instance for {tool_name}: {e}")
                continue
        
        return available_tools


# Global instance
_dynamic_registry: Optional[DynamicToolRegistry] = None


async def get_dynamic_tool_registry() -> DynamicToolRegistry:
    """Get or create the global dynamic tool registry"""
    global _dynamic_registry
    
    if _dynamic_registry is None:
        _dynamic_registry = DynamicToolRegistry()
        await _dynamic_registry.initialize()
    
    return _dynamic_registry


async def register_session_tools(session_id: str, model_id: str) -> SessionToolState:
    """Register tools for a session with a specific model"""
    registry = await get_dynamic_tool_registry()
    return await registry.register_session(session_id, model_id)


async def switch_session_model(session_id: str, new_model_id: str) -> ModelChangeEvent:
    """Switch model for a session and update tool availability"""
    registry = await get_dynamic_tool_registry()
    return await registry.switch_model(session_id, new_model_id)


async def validate_session_tool_call(session_id: str, tool_name: str) -> Tuple[bool, str]:
    """Validate if a tool call is available for the session"""
    registry = await get_dynamic_tool_registry()
    return await registry.validate_tool_call(session_id, tool_name)


async def get_session_available_tools(session_id: str, refresh_cache: bool = False) -> Dict[str, Any]:
    """Get available tools for a session"""
    registry = await get_dynamic_tool_registry()
    return await registry.get_available_tools(session_id, refresh_cache)


async def suggest_model_for_tools(session_id: str, required_tools: Set[str]) -> Optional[ModelCapability]:
    """Suggest a model switch if current model doesn't support required tools"""
    registry = await get_dynamic_tool_registry()
    return await registry.suggest_model_switch(session_id, required_tools) 