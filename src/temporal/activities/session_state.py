"""
Temporal activities for session state management
Handles session-specific tool availability, model capabilities, and configuration
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from temporalio import activity

from src.database.manager import db_manager
from src.models.capabilities import ModelCapabilityManager
from src.models.session_state import (
    SessionToolStateData, SessionConfiguration, ModelCapabilityInfo,
    ToolAvailabilityInfo, ModelCapabilityLevel, SessionToolState,
    session_state_manager, update_tool_availability_for_session,
    record_session_tool_execution
)
from src.tools.registry import tool_registry

logger = logging.getLogger(__name__)


@activity.defn
async def initialize_session_tool_state(session_id: str, model_id: str) -> Dict[str, Any]:
    """Initialize session tool state for a new session or model change"""
    try:
        # Get model capability information
        capability_manager = ModelCapabilityManager()
        model_capability = await capability_manager.get_model_capability(model_id)
        
        if not model_capability:
            logger.warning(f"No capability information found for model {model_id}")
            model_info = ModelCapabilityInfo(
                model_id=model_id,
                supports_tool_calls=False,
                capability_level=ModelCapabilityLevel.NONE
            )
        else:
            # Determine capability level based on model features
            capability_level = ModelCapabilityLevel.BASIC
            if model_capability.supports_tool_calls:
                if "advanced" in model_id.lower() or "gpt-4" in model_id.lower():
                    capability_level = ModelCapabilityLevel.ADVANCED
                elif "claude-3" in model_id.lower() or "gemini" in model_id.lower():
                    capability_level = ModelCapabilityLevel.EXPERT
            else:
                capability_level = ModelCapabilityLevel.NONE
            
            model_info = ModelCapabilityInfo(
                model_id=model_id,
                supports_tool_calls=model_capability.supports_tool_calls,
                capability_level=capability_level,
                max_tools_per_call=10,  # Default value since ModelCapability doesn't have this field
                context_length=model_capability.context_length or 4096
            )
        
        # Initialize session tool state
        tool_state = await db_manager.initialize_session_tool_state(
            session_id, model_id, model_info
        )
        
        if not tool_state:
            raise ValueError(f"Failed to initialize session tool state for {session_id}")
        
        # Register available tools for this model
        if model_info.supports_tool_calls:
            available_tools = tool_registry.list_tools(enabled_only=True)
            for tool_name in available_tools:
                await update_tool_availability_for_session(
                    session_id, tool_name, True
                )
        
        logger.info(f"Initialized session tool state for {session_id} with model {model_id}")
        
        return {
            "session_id": session_id,
            "model_id": model_id,
            "supports_tool_calls": model_info.supports_tool_calls,
            "capability_level": model_info.capability_level.value,
            "available_tools": tool_state.get_available_tools(),
            "configuration": {
                "enable_tools": tool_state.session_config.enable_tools,
                "max_concurrent_tools": tool_state.session_config.max_concurrent_tools,
                "tool_timeout_seconds": tool_state.session_config.tool_timeout_seconds
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to initialize session tool state: {e}")
        raise


@activity.defn
async def update_session_model(session_id: str, new_model_id: str) -> Dict[str, Any]:
    """Update session model and invalidate tool cache"""
    try:
        # Get new model capability information
        capability_manager = ModelCapabilityManager()
        model_capability = await capability_manager.get_model_capability(new_model_id)
        
        if not model_capability:
            logger.warning(f"No capability information found for model {new_model_id}")
            new_model_info = ModelCapabilityInfo(
                model_id=new_model_id,
                supports_tool_calls=False,
                capability_level=ModelCapabilityLevel.NONE
            )
        else:
            # Determine capability level
            capability_level = ModelCapabilityLevel.BASIC
            if model_capability.supports_tool_calls:
                if "advanced" in new_model_id.lower() or "gpt-4" in new_model_id.lower():
                    capability_level = ModelCapabilityLevel.ADVANCED
                elif "claude-3" in new_model_id.lower() or "gemini" in new_model_id.lower():
                    capability_level = ModelCapabilityLevel.EXPERT
            else:
                capability_level = ModelCapabilityLevel.NONE
            
            new_model_info = ModelCapabilityInfo(
                model_id=new_model_id,
                supports_tool_calls=model_capability.supports_tool_calls,
                capability_level=capability_level,
                max_tools_per_call=10,  # Default value since ModelCapability doesn't have this field
                context_length=model_capability.context_length or 4096
            )
        
        # Update model in session state manager
        updated_state = await session_state_manager.update_model_for_session(
            session_id, new_model_id, new_model_info
        )
        
        if not updated_state:
            raise ValueError(f"Failed to update model for session {session_id}")
        
        # Save updated state to database
        await db_manager.update_session_tool_state(session_id, updated_state)
        
        # Re-register tools for new model
        if new_model_info.supports_tool_calls:
            available_tools = tool_registry.list_tools(enabled_only=True)
            for tool_name in available_tools:
                await update_tool_availability_for_session(
                    session_id, tool_name, True
                )
        else:
            # Mark all tools as unavailable for non-tool-calling models
            current_state = await session_state_manager.get_session_state(session_id)
            if current_state:
                for tool_name in current_state.tool_availability.keys():
                    await update_tool_availability_for_session(
                        session_id, tool_name, False, "Model does not support tool calling"
                    )
        
        logger.info(f"Updated session {session_id} model to {new_model_id}")
        
        return {
            "session_id": session_id,
            "old_model": updated_state.current_model if updated_state.last_model_change else None,
            "new_model": new_model_id,
            "supports_tool_calls": new_model_info.supports_tool_calls,
            "capability_level": new_model_info.capability_level.value,
            "available_tools": updated_state.get_available_tools(),
            "model_switch_count": updated_state.model_switch_count
        }
        
    except Exception as e:
        logger.error(f"Failed to update session model: {e}")
        raise


@activity.defn
async def get_session_tool_availability(session_id: str) -> Dict[str, Any]:
    """Get current tool availability for a session"""
    try:
        session_state = await session_state_manager.get_session_state(session_id)
        
        if not session_state:
            logger.warning(f"No session state found for {session_id}")
            return {
                "session_id": session_id,
                "available_tools": [],
                "tool_availability": {},
                "supports_tool_calls": False,
                "model_id": None
            }
        
        # Build tool availability details
        tool_availability = {}
        for tool_name, info in session_state.tool_availability.items():
            tool_availability[tool_name] = {
                "state": info.state.value,
                "is_available": info.is_available(),
                "is_expired": info.is_expired(),
                "last_checked": info.last_checked.isoformat(),
                "cache_expiry": info.cache_expiry.isoformat() if info.cache_expiry else None,
                "error_message": info.error_message,
                "execution_count": info.execution_count,
                "success_count": info.success_count,
                "success_rate": info.get_success_rate(),
                "average_execution_time_ms": info.average_execution_time_ms
            }
        
        return {
            "session_id": session_id,
            "model_id": session_state.current_model,
            "supports_tool_calls": session_state.model_info.supports_tool_calls,
            "capability_level": session_state.model_info.capability_level.value,
            "available_tools": session_state.get_available_tools(),
            "tool_availability": tool_availability,
            "session_statistics": {
                "total_tool_calls": session_state.total_tool_calls,
                "successful_tool_calls": session_state.successful_tool_calls,
                "failed_tool_calls": session_state.failed_tool_calls,
                "success_rate": session_state.get_success_rate(),
                "cache_hit_rate": session_state.get_cache_hit_rate(),
                "model_switch_count": session_state.model_switch_count
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get session tool availability: {e}")
        raise


@activity.defn
async def update_session_tool_configuration(session_id: str, config_updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update session tool configuration"""
    try:
        # Get current configuration
        current_config = await db_manager.get_session_tool_configuration(session_id)
        
        if not current_config:
            # Create default configuration
            current_config = SessionConfiguration(session_id=session_id)
        
        # Apply updates
        if "enable_tools" in config_updates:
            current_config.enable_tools = config_updates["enable_tools"]
        if "max_concurrent_tools" in config_updates:
            current_config.max_concurrent_tools = config_updates["max_concurrent_tools"]
        if "tool_timeout_seconds" in config_updates:
            current_config.tool_timeout_seconds = config_updates["tool_timeout_seconds"]
        if "cache_duration_minutes" in config_updates:
            current_config.cache_duration_minutes = config_updates["cache_duration_minutes"]
        if "allowed_tools" in config_updates:
            current_config.allowed_tools = set(config_updates["allowed_tools"]) if config_updates["allowed_tools"] else None
        if "blocked_tools" in config_updates:
            current_config.blocked_tools = set(config_updates["blocked_tools"])
        if "tool_specific_config" in config_updates:
            current_config.tool_specific_config.update(config_updates["tool_specific_config"])
        
        current_config.updated_at = datetime.utcnow()
        
        # Save updated configuration
        success = await db_manager.update_session_tool_configuration(session_id, current_config)
        
        if not success:
            raise ValueError(f"Failed to update session tool configuration for {session_id}")
        
        logger.info(f"Updated session tool configuration for {session_id}")
        
        return {
            "session_id": session_id,
            "configuration": {
                "enable_tools": current_config.enable_tools,
                "max_concurrent_tools": current_config.max_concurrent_tools,
                "tool_timeout_seconds": current_config.tool_timeout_seconds,
                "cache_duration_minutes": current_config.cache_duration_minutes,
                "allowed_tools": list(current_config.allowed_tools) if current_config.allowed_tools else None,
                "blocked_tools": list(current_config.blocked_tools),
                "updated_at": current_config.updated_at.isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to update session tool configuration: {e}")
        raise


@activity.defn
async def refresh_tool_availability_cache(session_id: str, tool_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """Refresh tool availability cache for a session"""
    try:
        session_state = await session_state_manager.get_session_state(session_id)
        
        if not session_state:
            raise ValueError(f"No session state found for {session_id}")
        
        # Determine which tools to refresh
        if tool_names is None:
            tool_names = list(session_state.tool_availability.keys())
        
        refreshed_tools = []
        failed_tools = []
        
        # Check if model supports tool calls
        if not session_state.model_info.supports_tool_calls:
            # Mark all tools as unavailable
            for tool_name in tool_names:
                await update_tool_availability_for_session(
                    session_id, tool_name, False, "Model does not support tool calling"
                )
                refreshed_tools.append(tool_name)
        else:
            # Refresh each tool's availability
            available_tools = tool_registry.list_tools(enabled_only=True)
            
            for tool_name in tool_names:
                try:
                    is_available = tool_name in available_tools
                    error_message = None if is_available else "Tool not found in registry"
                    
                    await update_tool_availability_for_session(
                        session_id, tool_name, is_available, error_message
                    )
                    refreshed_tools.append(tool_name)
                    
                except Exception as e:
                    logger.error(f"Failed to refresh tool {tool_name} for session {session_id}: {e}")
                    await update_tool_availability_for_session(
                        session_id, tool_name, False, str(e)
                    )
                    failed_tools.append(tool_name)
        
        # Update cache refresh count
        updated_state = await session_state_manager.get_session_state(session_id)
        if updated_state:
            updated_state.cache_refresh_count += 1
            await db_manager.update_session_tool_state(session_id, updated_state)
        
        logger.info(f"Refreshed tool availability cache for session {session_id}: {len(refreshed_tools)} tools")
        
        return {
            "session_id": session_id,
            "refreshed_tools": refreshed_tools,
            "failed_tools": failed_tools,
            "refresh_count": updated_state.cache_refresh_count if updated_state else 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to refresh tool availability cache: {e}")
        raise


@activity.defn
async def record_tool_execution_for_session(session_id: str, tool_name: str, success: bool, execution_time_ms: float) -> Dict[str, Any]:
    """Record a tool execution for session analytics"""
    try:
        # Record in session state manager
        await record_session_tool_execution(session_id, tool_name, success, execution_time_ms)
        
        # Get updated session state
        session_state = await session_state_manager.get_session_state(session_id)
        
        if session_state:
            # Save updated state to database
            await db_manager.update_session_tool_state(session_id, session_state)
            
            tool_info = session_state.get_tool_info(tool_name)
            
            return {
                "session_id": session_id,
                "tool_name": tool_name,
                "success": success,
                "execution_time_ms": execution_time_ms,
                "session_statistics": {
                    "total_tool_calls": session_state.total_tool_calls,
                    "successful_tool_calls": session_state.successful_tool_calls,
                    "failed_tool_calls": session_state.failed_tool_calls,
                    "success_rate": session_state.get_success_rate()
                },
                "tool_statistics": {
                    "execution_count": tool_info.execution_count if tool_info else 0,
                    "success_count": tool_info.success_count if tool_info else 0,
                    "success_rate": tool_info.get_success_rate() if tool_info else 0.0,
                    "average_execution_time_ms": tool_info.average_execution_time_ms if tool_info else 0.0
                } if tool_info else None
            }
        
        return {
            "session_id": session_id,
            "tool_name": tool_name,
            "success": success,
            "execution_time_ms": execution_time_ms,
            "error": "Session state not found"
        }
        
    except Exception as e:
        logger.error(f"Failed to record tool execution for session: {e}")
        raise


@activity.defn
async def get_session_tool_statistics(session_id: str) -> Dict[str, Any]:
    """Get comprehensive session tool statistics"""
    try:
        # Get from session state manager
        stats = await session_state_manager.get_session_statistics(session_id)
        
        if not stats:
            return {
                "session_id": session_id,
                "error": "Session state not found"
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get session tool statistics: {e}")
        raise


@activity.defn
async def cleanup_expired_session_states(max_age_hours: int = 24) -> Dict[str, Any]:
    """Clean up expired session states"""
    try:
        cleaned_count = await session_state_manager.cleanup_expired_sessions(max_age_hours)
        
        # Get current statistics
        all_stats = await session_state_manager.get_all_session_stats()
        
        logger.info(f"Cleaned up {cleaned_count} expired session states")
        
        return {
            "cleaned_sessions": cleaned_count,
            "remaining_sessions": all_stats["total_sessions"],
            "active_sessions": all_stats["active_sessions"],
            "cleanup_timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired session states: {e}")
        raise 