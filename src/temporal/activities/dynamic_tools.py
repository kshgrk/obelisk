"""
Temporal Activities for Dynamic Tool Registration
Handles model switching and tool availability management
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Any, Tuple
from temporalio import activity

from src.models.dynamic_tools import (
    get_dynamic_tool_registry,
    register_session_tools,
    switch_session_model,
    validate_session_tool_call,
    get_session_available_tools,
    suggest_model_for_tools,
    SessionToolState,
    ModelChangeEvent,
    ToolAvailabilityStatus
)

logger = logging.getLogger(__name__)


class DynamicToolActivities:
    """Temporal activities for dynamic tool registration"""

    @staticmethod
    @activity.defn
    async def register_session_for_dynamic_tools(session_id: str, model_id: str) -> Dict[str, Any]:
        """Register a session with the dynamic tool registry"""
        try:
            activity.logger.info(f"Registering session {session_id} with model {model_id} for dynamic tools")
            
            session_state = await register_session_tools(session_id, model_id)
            
            result = {
                "success": True,
                "session_id": session_id,
                "model_id": model_id,
                "available_tools": list(session_state.available_tools),
                "tool_count": len(session_state.available_tools),
                "registration_time": session_state.last_model_change.isoformat() if session_state.last_model_change else None
            }
            
            activity.logger.info(f"Successfully registered session {session_id} with {len(session_state.available_tools)} tools")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to register session {session_id} for dynamic tools: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id,
                "model_id": model_id
            }

    @staticmethod
    @activity.defn
    async def switch_session_model_dynamic(session_id: str, new_model_id: str) -> Dict[str, Any]:
        """Switch model for a session and update tool availability"""
        try:
            activity.logger.info(f"Switching model for session {session_id} to {new_model_id}")
            
            change_event = await switch_session_model(session_id, new_model_id)
            
            result = {
                "success": True,
                "session_id": session_id,
                "old_model": change_event.old_model,
                "new_model": change_event.new_model,
                "tools_before": list(change_event.tools_before),
                "tools_after": list(change_event.tools_after),
                "tools_added": list(change_event.tools_added),
                "tools_removed": list(change_event.tools_removed),
                "switch_timestamp": change_event.timestamp.isoformat(),
                "change_summary": {
                    "total_tools_before": len(change_event.tools_before),
                    "total_tools_after": len(change_event.tools_after),
                    "tools_added_count": len(change_event.tools_added),
                    "tools_removed_count": len(change_event.tools_removed)
                }
            }
            
            activity.logger.info(f"Model switch completed for session {session_id}: "
                               f"{change_event.old_model} → {change_event.new_model}, "
                               f"tools: +{len(change_event.tools_added)} -{len(change_event.tools_removed)}")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to switch model for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id,
                "new_model_id": new_model_id
            }

    @staticmethod
    @activity.defn
    async def validate_tool_call_for_session(session_id: str, tool_name: str) -> Dict[str, Any]:
        """Validate if a tool call is available for the session"""
        try:
            activity.logger.debug(f"Validating tool call '{tool_name}' for session {session_id}")
            
            is_valid, message = await validate_session_tool_call(session_id, tool_name)
            
            result = {
                "success": True,
                "session_id": session_id,
                "tool_name": tool_name,
                "is_valid": is_valid,
                "validation_message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if is_valid:
                activity.logger.debug(f"Tool call '{tool_name}' validated for session {session_id}")
            else:
                activity.logger.warning(f"Tool call '{tool_name}' validation failed for session {session_id}: {message}")
            
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to validate tool call '{tool_name}' for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id,
                "tool_name": tool_name,
                "is_valid": False
            }

    @staticmethod
    @activity.defn
    async def get_session_tools(session_id: str, refresh_cache: bool = False) -> Dict[str, Any]:
        """Get available tools for a session"""
        try:
            activity.logger.debug(f"Getting available tools for session {session_id} (refresh: {refresh_cache})")
            
            available_tools = await get_session_available_tools(session_id, refresh_cache)
            
            # Convert tool data for serialization
            serializable_tools = {}
            for tool_name, tool_data in available_tools.items():
                serializable_tools[tool_name] = {
                    "name": tool_data["name"],
                    "description": tool_data["description"],
                    "parameters": tool_data["parameters"]
                    # Exclude "instance" as it's not serializable
                }
            
            result = {
                "success": True,
                "session_id": session_id,
                "available_tools": serializable_tools,
                "tool_count": len(available_tools),
                "cache_refreshed": refresh_cache,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            activity.logger.debug(f"Retrieved {len(available_tools)} tools for session {session_id}")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to get tools for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id,
                "available_tools": {},
                "tool_count": 0
            }

    @staticmethod
    @activity.defn
    async def suggest_model_switch_for_tools(session_id: str, required_tools: List[str]) -> Dict[str, Any]:
        """Suggest a model switch if current model doesn't support required tools"""
        try:
            activity.logger.info(f"Suggesting model switch for session {session_id} with required tools: {required_tools}")
            
            required_tools_set = set(required_tools)
            suggested_model = await suggest_model_for_tools(session_id, required_tools_set)
            
            result = {
                "success": True,
                "session_id": session_id,
                "required_tools": required_tools,
                "switch_needed": suggested_model is not None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if suggested_model:
                result["suggested_model"] = {
                    "model_id": suggested_model.model_id,
                    "name": suggested_model.name,
                    "supports_tool_calls": suggested_model.supports_tool_calls,
                    "context_length": suggested_model.context_length
                }
                activity.logger.info(f"Suggested model switch for session {session_id}: {suggested_model.model_id}")
            else:
                result["suggested_model"] = None
                activity.logger.info(f"No model switch needed for session {session_id}")
            
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to suggest model switch for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id,
                "required_tools": required_tools,
                "switch_needed": False,
                "suggested_model": None
            }

    @staticmethod
    @activity.defn
    async def get_tool_compatibility_matrix() -> Dict[str, Any]:
        """Get compatibility matrix of tools vs models"""
        try:
            activity.logger.info("Generating tool compatibility matrix")
            
            registry = await get_dynamic_tool_registry()
            matrix = await registry.get_tool_compatibility_matrix()
            
            # Convert enum values to strings for serialization
            serializable_matrix = {}
            for model_id, model_tools in matrix.items():
                serializable_matrix[model_id] = {
                    tool_name: status.value if hasattr(status, 'value') else str(status)
                    for tool_name, status in model_tools.items()
                }
            
            result = {
                "success": True,
                "compatibility_matrix": serializable_matrix,
                "model_count": len(matrix),
                "tool_count": len(next(iter(matrix.values()))) if matrix else 0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            activity.logger.info(f"Generated compatibility matrix: {len(matrix)} models, "
                               f"{len(next(iter(matrix.values()))) if matrix else 0} tools")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to generate tool compatibility matrix: {e}")
            return {
                "success": False,
                "error": str(e),
                "compatibility_matrix": {},
                "model_count": 0,
                "tool_count": 0
            }

    @staticmethod
    @activity.defn
    async def get_session_tool_state(session_id: str) -> Dict[str, Any]:
        """Get detailed tool state for a session"""
        try:
            activity.logger.debug(f"Getting tool state for session {session_id}")
            
            registry = await get_dynamic_tool_registry()
            session_state = await registry.get_session_state(session_id)
            
            if session_state is None:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found in dynamic tool registry",
                    "session_id": session_id
                }
            
            result = {
                "success": True,
                "session_id": session_id,
                "current_model": session_state.current_model,
                "available_tools": list(session_state.available_tools),
                "tool_count": len(session_state.available_tools),
                "last_model_change": session_state.last_model_change.isoformat() if session_state.last_model_change else None,
                "tool_cache_expiry": session_state.tool_cache_expiry.isoformat() if session_state.tool_cache_expiry else None,
                "model_switch_count": session_state.model_switch_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            activity.logger.debug(f"Retrieved tool state for session {session_id}: "
                                f"model={session_state.current_model}, tools={len(session_state.available_tools)}")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to get tool state for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }

    @staticmethod
    @activity.defn
    async def get_model_change_history(session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get model change history, optionally filtered by session"""
        try:
            activity.logger.debug(f"Getting model change history for session: {session_id or 'all'}")
            
            registry = await get_dynamic_tool_registry()
            change_events = await registry.get_model_change_history(session_id)
            
            # Convert events to serializable format
            serializable_events = []
            for event in change_events:
                serializable_events.append({
                    "session_id": event.session_id,
                    "old_model": event.old_model,
                    "new_model": event.new_model,
                    "timestamp": event.timestamp.isoformat(),
                    "tools_before": list(event.tools_before),
                    "tools_after": list(event.tools_after),
                    "tools_added": list(event.tools_added),
                    "tools_removed": list(event.tools_removed),
                    "change_summary": {
                        "tools_added_count": len(event.tools_added),
                        "tools_removed_count": len(event.tools_removed),
                        "net_change": len(event.tools_added) - len(event.tools_removed)
                    }
                })
            
            result = {
                "success": True,
                "session_filter": session_id,
                "change_events": serializable_events,
                "event_count": len(change_events),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            activity.logger.debug(f"Retrieved {len(change_events)} model change events")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to get model change history: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_filter": session_id,
                "change_events": [],
                "event_count": 0
            }

    @staticmethod
    @activity.defn
    async def cleanup_session_tools(session_id: str) -> Dict[str, Any]:
        """Clean up session data from dynamic tool registry"""
        try:
            activity.logger.info(f"Cleaning up session {session_id} from dynamic tool registry")
            
            registry = await get_dynamic_tool_registry()
            cleaned_up = await registry.cleanup_session(session_id)
            
            result = {
                "success": True,
                "session_id": session_id,
                "was_registered": cleaned_up,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if cleaned_up:
                activity.logger.info(f"Successfully cleaned up session {session_id}")
            else:
                activity.logger.warning(f"Session {session_id} was not registered in dynamic tool registry")
            
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to cleanup session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id,
                "was_registered": False
            } 