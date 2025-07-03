"""
Session State Management for Dynamic Tool Registration
Handles session-specific tool availability, model capabilities, and configuration
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

logger = logging.getLogger(__name__)


class SessionToolState(str, Enum):
    """Session tool availability states"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    LOADING = "loading"
    ERROR = "error"
    CACHED = "cached"
    EXPIRED = "expired"


class ModelCapabilityLevel(str, Enum):
    """Model capability levels for tool support"""
    NONE = "none"           # No tool calling support
    BASIC = "basic"         # Basic function calling
    ADVANCED = "advanced"   # Advanced tool calling with complex parameters
    EXPERT = "expert"       # Expert level with tool chaining and complex workflows


@dataclass
class ToolAvailabilityInfo:
    """Information about tool availability for a session"""
    tool_name: str
    state: SessionToolState
    last_checked: datetime
    cache_expiry: Optional[datetime] = None
    error_message: Optional[str] = None
    execution_count: int = 0
    success_count: int = 0
    average_execution_time_ms: float = 0.0
    last_execution_time: Optional[datetime] = None
    configuration: Dict[str, Any] = field(default_factory=dict)
    
    def is_available(self) -> bool:
        """Check if tool is currently available"""
        return self.state in [SessionToolState.AVAILABLE, SessionToolState.CACHED]
    
    def is_expired(self) -> bool:
        """Check if cached tool availability has expired"""
        if self.cache_expiry is None:
            return False
        return datetime.utcnow() > self.cache_expiry
    
    def get_success_rate(self) -> float:
        """Get tool success rate as percentage"""
        if self.execution_count == 0:
            return 0.0
        return (self.success_count / self.execution_count) * 100


@dataclass
class ModelCapabilityInfo:
    """Information about model capabilities for a session"""
    model_id: str
    supports_tool_calls: bool
    capability_level: ModelCapabilityLevel
    max_tools_per_call: int = 10
    max_parallel_tools: int = 5
    supported_tool_types: Set[str] = field(default_factory=set)
    context_length: int = 4096
    last_verified: datetime = field(default_factory=datetime.utcnow)
    verification_expiry: Optional[datetime] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def is_verification_expired(self) -> bool:
        """Check if model capability verification has expired"""
        if self.verification_expiry is None:
            return False
        return datetime.utcnow() > self.verification_expiry
    
    def supports_tool_type(self, tool_type: str) -> bool:
        """Check if model supports a specific tool type"""
        return tool_type in self.supported_tool_types or len(self.supported_tool_types) == 0


@dataclass
class SessionConfiguration:
    """Session-specific tool configuration"""
    session_id: str
    enable_tools: bool = True
    max_concurrent_tools: int = 3
    tool_timeout_seconds: float = 30.0
    auto_retry_failed_tools: bool = True
    max_tool_retries: int = 2
    cache_tool_results: bool = True
    cache_duration_minutes: int = 30
    allowed_tools: Optional[Set[str]] = None  # None means all tools allowed
    blocked_tools: Set[str] = field(default_factory=set)
    tool_specific_config: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    rate_limits: Dict[str, int] = field(default_factory=dict)  # tool_name -> calls_per_minute
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed for this session"""
        if tool_name in self.blocked_tools:
            return False
        if self.allowed_tools is None:
            return True
        return tool_name in self.allowed_tools
    
    def get_tool_config(self, tool_name: str) -> Dict[str, Any]:
        """Get tool-specific configuration"""
        return self.tool_specific_config.get(tool_name, {})
    
    def get_rate_limit(self, tool_name: str) -> Optional[int]:
        """Get rate limit for a specific tool"""
        return self.rate_limits.get(tool_name)


@dataclass
class SessionToolStateData:
    """Complete tool state for a session"""
    session_id: str
    current_model: str
    model_info: ModelCapabilityInfo
    tool_availability: Dict[str, ToolAvailabilityInfo] = field(default_factory=dict)
    session_config: SessionConfiguration = field(default_factory=lambda: SessionConfiguration(""))
    last_model_change: Optional[datetime] = None
    model_switch_count: int = 0
    cache_refresh_count: int = 0
    total_tool_calls: int = 0
    successful_tool_calls: int = 0
    failed_tool_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Initialize session configuration with correct session_id"""
        if self.session_config.session_id != self.session_id:
            self.session_config.session_id = self.session_id
    
    def get_available_tools(self) -> List[str]:
        """Get list of currently available tools"""
        available = []
        for tool_name, info in self.tool_availability.items():
            if info.is_available() and not info.is_expired():
                if self.session_config.is_tool_allowed(tool_name):
                    available.append(tool_name)
        return available
    
    def get_tool_info(self, tool_name: str) -> Optional[ToolAvailabilityInfo]:
        """Get availability info for a specific tool"""
        return self.tool_availability.get(tool_name)
    
    def add_tool_execution(self, tool_name: str, success: bool, execution_time_ms: float):
        """Record a tool execution"""
        self.total_tool_calls += 1
        if success:
            self.successful_tool_calls += 1
        else:
            self.failed_tool_calls += 1
        
        # Update tool-specific stats
        if tool_name in self.tool_availability:
            info = self.tool_availability[tool_name]
            info.execution_count += 1
            if success:
                info.success_count += 1
            
            # Update average execution time
            if info.execution_count == 1:
                info.average_execution_time_ms = execution_time_ms
            else:
                # Exponential moving average
                alpha = 0.3  # Weight for new value
                info.average_execution_time_ms = (
                    alpha * execution_time_ms + 
                    (1 - alpha) * info.average_execution_time_ms
                )
            
            info.last_execution_time = datetime.utcnow()
        
        self.updated_at = datetime.utcnow()
    
    def get_success_rate(self) -> float:
        """Get overall session tool success rate"""
        if self.total_tool_calls == 0:
            return 0.0
        return (self.successful_tool_calls / self.total_tool_calls) * 100
    
    def get_cache_hit_rate(self) -> float:
        """Get cache hit rate"""
        total_requests = self.cache_hits + self.cache_misses
        if total_requests == 0:
            return 0.0
        return (self.cache_hits / total_requests) * 100
    
    def needs_refresh(self, tool_name: str) -> bool:
        """Check if a tool's availability needs to be refreshed"""
        if tool_name not in self.tool_availability:
            return True
        
        info = self.tool_availability[tool_name]
        return info.is_expired() or info.state == SessionToolState.ERROR
    
    def mark_cache_hit(self):
        """Mark a cache hit"""
        self.cache_hits += 1
        self.updated_at = datetime.utcnow()
    
    def mark_cache_miss(self):
        """Mark a cache miss"""
        self.cache_misses += 1
        self.updated_at = datetime.utcnow()


class SessionStateManager:
    """Manages session states for tool availability and model capabilities"""
    
    def __init__(self, default_cache_duration_minutes: int = 30):
        self._session_states: Dict[str, SessionToolStateData] = {}
        self._lock = asyncio.Lock()
        self.default_cache_duration = timedelta(minutes=default_cache_duration_minutes)
        self.cleanup_interval = timedelta(hours=1)
        self.last_cleanup = datetime.utcnow()
    
    async def get_session_state(self, session_id: str) -> Optional[SessionToolStateData]:
        """Get session state by ID"""
        async with self._lock:
            return self._session_states.get(session_id)
    
    async def create_session_state(self, 
                                 session_id: str, 
                                 model_id: str,
                                 model_info: ModelCapabilityInfo,
                                 session_config: Optional[SessionConfiguration] = None) -> SessionToolStateData:
        """Create a new session state"""
        async with self._lock:
            if session_config is None:
                session_config = SessionConfiguration(session_id)
            
            state = SessionToolStateData(
                session_id=session_id,
                current_model=model_id,
                model_info=model_info,
                session_config=session_config
            )
            
            self._session_states[session_id] = state
            return state
    
    async def update_model_for_session(self, 
                                     session_id: str, 
                                     new_model_id: str,
                                     new_model_info: ModelCapabilityInfo) -> Optional[SessionToolStateData]:
        """Update model for a session and invalidate tool cache"""
        async with self._lock:
            state = self._session_states.get(session_id)
            if not state:
                return None
            
            # Record model change
            old_model = state.current_model
            state.current_model = new_model_id
            state.model_info = new_model_info
            state.last_model_change = datetime.utcnow()
            state.model_switch_count += 1
            state.updated_at = datetime.utcnow()
            
            # Invalidate tool availability cache since model changed
            for tool_info in state.tool_availability.values():
                tool_info.state = SessionToolState.EXPIRED
                tool_info.last_checked = datetime.utcnow()
            
            logger.info(f"Updated model for session {session_id}: {old_model} → {new_model_id}")
            return state
    
    async def update_tool_availability(self, 
                                     session_id: str, 
                                     tool_name: str,
                                     is_available: bool,
                                     error_message: Optional[str] = None,
                                     cache_duration: Optional[timedelta] = None) -> bool:
        """Update tool availability for a session"""
        async with self._lock:
            state = self._session_states.get(session_id)
            if not state:
                return False
            
            cache_duration = cache_duration or self.default_cache_duration
            
            # Create or update tool availability info
            if tool_name not in state.tool_availability:
                state.tool_availability[tool_name] = ToolAvailabilityInfo(
                    tool_name=tool_name,
                    state=SessionToolState.LOADING,
                    last_checked=datetime.utcnow()
                )
            
            info = state.tool_availability[tool_name]
            info.state = SessionToolState.AVAILABLE if is_available else SessionToolState.UNAVAILABLE
            info.last_checked = datetime.utcnow()
            info.cache_expiry = datetime.utcnow() + cache_duration
            info.error_message = error_message
            
            state.updated_at = datetime.utcnow()
            return True
    
    async def update_session_configuration(self, 
                                         session_id: str, 
                                         config: SessionConfiguration) -> bool:
        """Update session configuration"""
        async with self._lock:
            state = self._session_states.get(session_id)
            if not state:
                return False
            
            config.session_id = session_id
            config.updated_at = datetime.utcnow()
            state.session_config = config
            state.updated_at = datetime.utcnow()
            return True
    
    async def record_tool_execution(self, 
                                  session_id: str, 
                                  tool_name: str,
                                  success: bool,
                                  execution_time_ms: float) -> bool:
        """Record a tool execution for analytics"""
        async with self._lock:
            state = self._session_states.get(session_id)
            if not state:
                return False
            
            state.add_tool_execution(tool_name, success, execution_time_ms)
            return True
    
    async def cleanup_expired_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up expired session states"""
        async with self._lock:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            expired_sessions = [
                session_id for session_id, state in self._session_states.items()
                if state.updated_at < cutoff_time
            ]
            
            for session_id in expired_sessions:
                del self._session_states[session_id]
            
            self.last_cleanup = datetime.utcnow()
            logger.info(f"Cleaned up {len(expired_sessions)} expired session states")
            return len(expired_sessions)
    
    async def get_session_statistics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive session statistics"""
        async with self._lock:
            state = self._session_states.get(session_id)
            if not state:
                return None
            
            available_tools = state.get_available_tools()
            
            return {
                "session_id": session_id,
                "current_model": state.current_model,
                "model_capability_level": state.model_info.capability_level.value,
                "supports_tool_calls": state.model_info.supports_tool_calls,
                "available_tools_count": len(available_tools),
                "available_tools": available_tools,
                "total_tool_calls": state.total_tool_calls,
                "successful_tool_calls": state.successful_tool_calls,
                "failed_tool_calls": state.failed_tool_calls,
                "success_rate_percent": state.get_success_rate(),
                "cache_hit_rate_percent": state.get_cache_hit_rate(),
                "model_switch_count": state.model_switch_count,
                "last_model_change": state.last_model_change.isoformat() if state.last_model_change else None,
                "session_age_hours": (datetime.utcnow() - state.created_at).total_seconds() / 3600,
                "configuration": {
                    "enable_tools": state.session_config.enable_tools,
                    "max_concurrent_tools": state.session_config.max_concurrent_tools,
                    "tool_timeout_seconds": state.session_config.tool_timeout_seconds,
                    "cache_duration_minutes": state.session_config.cache_duration_minutes,
                    "allowed_tools_count": len(state.session_config.allowed_tools) if state.session_config.allowed_tools else None,
                    "blocked_tools_count": len(state.session_config.blocked_tools)
                }
            }
    
    async def get_all_session_stats(self) -> Dict[str, Any]:
        """Get statistics for all active sessions"""
        async with self._lock:
            total_sessions = len(self._session_states)
            active_sessions = sum(1 for state in self._session_states.values() 
                                if (datetime.utcnow() - state.updated_at).total_seconds() < 3600)
            
            total_tool_calls = sum(state.total_tool_calls for state in self._session_states.values())
            total_successful = sum(state.successful_tool_calls for state in self._session_states.values())
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "total_tool_calls": total_tool_calls,
                "total_successful_calls": total_successful,
                "overall_success_rate": (total_successful / total_tool_calls * 100) if total_tool_calls > 0 else 0,
                "last_cleanup": self.last_cleanup.isoformat(),
                "memory_usage_mb": len(str(self._session_states)) / 1024 / 1024  # Rough estimate
            }
    
    async def remove_session(self, session_id: str) -> bool:
        """Remove a session state"""
        async with self._lock:
            if session_id in self._session_states:
                del self._session_states[session_id]
                logger.info(f"Removed session state for {session_id}")
                return True
            return False


# Global session state manager instance
session_state_manager = SessionStateManager()


# Helper functions for easy access
async def get_session_tool_state(session_id: str) -> Optional[SessionToolStateData]:
    """Get session tool state"""
    return await session_state_manager.get_session_state(session_id)


async def create_session_tool_state(session_id: str, 
                                   model_id: str,
                                   model_info: ModelCapabilityInfo,
                                   config: Optional[SessionConfiguration] = None) -> SessionToolStateData:
    """Create session tool state"""
    return await session_state_manager.create_session_state(session_id, model_id, model_info, config)


async def update_session_model(session_id: str, 
                              new_model_id: str,
                              new_model_info: ModelCapabilityInfo) -> Optional[SessionToolStateData]:
    """Update session model"""
    return await session_state_manager.update_model_for_session(session_id, new_model_id, new_model_info)


async def update_tool_availability_for_session(session_id: str, 
                                              tool_name: str,
                                              is_available: bool,
                                              error_message: Optional[str] = None) -> bool:
    """Update tool availability for session"""
    return await session_state_manager.update_tool_availability(session_id, tool_name, is_available, error_message)


async def record_session_tool_execution(session_id: str, 
                                       tool_name: str,
                                       success: bool,
                                       execution_time_ms: float) -> bool:
    """Record tool execution for session"""
    return await session_state_manager.record_tool_execution(session_id, tool_name, success, execution_time_ms) 