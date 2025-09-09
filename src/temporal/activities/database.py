"""
Database activities for Temporal workflows using optimized conversation_turns structure
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import uuid4

from temporalio import activity

from src.database.manager import db_manager
from src.models.chat import ChatMessageCreate, MessageRole

logger = logging.getLogger(__name__)


class DatabaseActivities:
    """Database activities for conversation turn management"""

    @staticmethod
    @activity.defn
    async def create_session(name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new chat session"""
        try:
            from src.models.chat import ChatSessionCreate

            session_data = ChatSessionCreate(name=name)
            session = await db_manager.create_session(session_data)

            return {
                "session_id": session.id,
                "name": session.name,
                "status": session.status.value,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "message_count": session.message_count
            }
            
        except Exception as e:
            activity.logger.error(f"Failed to create session: {e}")
            raise

    @staticmethod
    @activity.defn
    async def create_session_with_id(session_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new chat session with a specific session_id"""
        try:
            from src.models.chat import ChatSessionCreate

            # Create session data with the specific session_id
            session_data = ChatSessionCreate(name=name)
            # Use the custom session_id parameter
            session = await db_manager.create_session(session_data, custom_session_id=session_id)

            return {
                "success": True,
                "session_id": session.id,
                "name": session.name,
                "status": session.status,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "message_count": session.message_count
            }

        except Exception as e:
            activity.logger.error(f"Failed to create session with id {session_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    @activity.defn
    async def save_conversation_turn(session_id: str, turn_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a complete conversation turn atomically"""
        try:
            # Ensure turn has proper structure and IDs
            if "turn_id" not in turn_data:
                turn_data["turn_id"] = f"turn_{str(uuid4())[:8]}"
            
            if "turn_number" not in turn_data:
                # Get current turn count and increment
                conversation = await db_manager.get_conversation_history(session_id)
                turn_data["turn_number"] = len(conversation.get("conversation_turns", [])) + 1
            
            # Save the complete turn
            saved_turn = await db_manager.add_conversation_turn(session_id, turn_data)
            
            activity.logger.info(f"Saved conversation turn {turn_data['turn_id']} to session {session_id}")
            return saved_turn
            
        except Exception as e:
            activity.logger.error(f"Failed to save conversation turn: {e}")
            raise

    @staticmethod
    @activity.defn
    async def get_conversation_context(session_id: str, max_turns: int = 5) -> Dict[str, Any]:
        """Get recent conversation context for AI processing"""
        try:
            context = await db_manager.get_session_context(session_id, limit=max_turns)
            
            activity.logger.debug(f"Retrieved conversation context for session {session_id}: {len(context['messages'])} messages")
            return context
            
        except Exception as e:
            activity.logger.error(f"Failed to get conversation context: {e}")
            raise

    @staticmethod
    @activity.defn
    async def get_full_conversation(session_id: str) -> Dict[str, Any]:
        """Get the complete conversation history"""
        try:
            conversation = await db_manager.get_conversation_history(session_id)
            
            activity.logger.debug(f"Retrieved full conversation for session {session_id}")
            return conversation
            
        except Exception as e:
            activity.logger.error(f"Failed to get full conversation: {e}")
            raise

    @staticmethod
    @activity.defn
    async def update_session_metadata(session_id: str, metadata_updates: Dict[str, Any]) -> bool:
        """Update session metadata (statistics, settings, etc.)"""
        try:
            async with db_manager.get_connection() as db:
                await db.execute("BEGIN")
                try:
                    # Get current session data
                    cursor = await db.execute(
                        "SELECT session_data FROM sessions WHERE session_id = ?",
                        (session_id,)
                    )
                    row = await cursor.fetchone()
                    
                    if not row:
                        return False
                    
                    # Update session data structure
                    current_session_data = json.loads(row['session_data']) if row['session_data'] else {}
                    current_metadata = current_session_data.get('metadata', {})
                    current_metadata.update(metadata_updates)
                    current_metadata['last_updated'] = datetime.utcnow().isoformat()
                    
                    # Update session_data with new metadata
                    current_session_data['metadata'] = current_metadata
                    
                    # Save updated session data
                    await db.execute(
                        "UPDATE sessions SET session_data = ?, updated_at = ? WHERE session_id = ?",
                        (json.dumps(current_session_data), datetime.utcnow().isoformat(), session_id)
                    )
                    
                    await db.commit()
                    activity.logger.debug(f"Updated session metadata for {session_id}")
                    return True
                    
                except Exception:
                    await db.rollback()
                    raise
            
        except Exception as e:
            activity.logger.error(f"Failed to update session metadata: {e}")
            raise

    @staticmethod
    @activity.defn
    async def get_session_info(session_id: str) -> Dict[str, Any]:
        """Get session information"""
        try:
            session = await db_manager.get_session(session_id)
            
            if not session:
                return {"found": False}
            
            return {
                "found": True,
                "session_id": session.id,
                "name": session.name,
                "status": session.status.value,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "message_count": session.message_count,
                "metadata": session.metadata
            }
            
        except Exception as e:
            activity.logger.error(f"Failed to get session info: {e}")
            raise

    # Legacy compatibility method - DISABLED for pure JSON conversation_turns approach
    @staticmethod
    @activity.defn
    async def add_message(session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy method - DISABLED. 
        Use save_conversation_turn() for complete conversation turns in pure JSON storage.
        """
        activity.logger.error("Legacy add_message() called - use save_conversation_turn() instead")
        raise NotImplementedError(
            "Legacy add_message() disabled. Use save_conversation_turn() for complete conversation turns."
        )

    @staticmethod
    @activity.defn
    async def get_session_context(session_id: str, limit: int = 5) -> Dict[str, Any]:
        """Legacy method - get recent messages for context"""
        try:
            context = await db_manager.get_session_context(session_id, limit)
            activity.logger.debug(f"Retrieved {len(context['messages'])} context messages for session {session_id}")
            return context
            
        except Exception as e:
            activity.logger.error(f"Failed to get session context: {e}")
            raise

    @staticmethod
    @activity.defn
    async def update_tool_statistics_for_session(session_id: str, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Update tool usage statistics for a session based on tool execution results"""
        try:
            activity.logger.info(f"Updating tool statistics for session {session_id} with {len(tool_results)} tool results")
            
            statistics_summary = {
                "total_updated": 0,
                "successful_tools": 0,
                "failed_tools": 0,
                "cancelled_tools": 0,
                "tools_processed": []
            }
            
            for tool_result in tool_results:
                try:
                    tool_name = tool_result.get("tool_name", "unknown")
                    execution_time = tool_result.get("execution_time_seconds", 0.0)
                    success = tool_result.get("success", False)
                    status = tool_result.get("status", "unknown")
                    cancelled = status in ["cancelled", "timeout"]
                    
                    # Update individual tool statistics
                    await db_manager.update_tool_statistics(
                        session_id=session_id,
                        tool_name=tool_name,
                        execution_time=execution_time,
                        success=success,
                        cancelled=cancelled
                    )
                    
                    statistics_summary["total_updated"] += 1
                    statistics_summary["tools_processed"].append({
                        "tool_name": tool_name,
                        "success": success,
                        "execution_time": execution_time,
                        "status": status
                    })
                    
                    if cancelled:
                        statistics_summary["cancelled_tools"] += 1
                    elif success:
                        statistics_summary["successful_tools"] += 1
                    else:
                        statistics_summary["failed_tools"] += 1
                        
                except Exception as e:
                    activity.logger.warning(f"Failed to update statistics for tool {tool_result.get('tool_name', 'unknown')}: {e}")
                    continue
            
            activity.logger.info(f"Tool statistics update completed for session {session_id}: {statistics_summary['total_updated']} tools processed")
            return {
                "success": True,
                "session_id": session_id,
                "statistics_summary": statistics_summary,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            activity.logger.error(f"Failed to update tool statistics for session {session_id}: {e}")
            return {
                "success": False,
                "session_id": session_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    @staticmethod
    @activity.defn
    async def get_session_tool_statistics(session_id: str) -> Dict[str, Any]:
        """Get tool usage statistics for a specific session"""
        try:
            statistics = await db_manager.get_tool_statistics(session_id)
            
            activity.logger.debug(f"Retrieved tool statistics for session {session_id}")
            return {
                "success": True,
                "session_id": session_id,
                "statistics": statistics,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            activity.logger.error(f"Failed to get tool statistics for session {session_id}: {e}")
            return {
                "success": False,
                "session_id": session_id,
                "error": str(e),
                "statistics": {},
                "timestamp": datetime.utcnow().isoformat()
            }

    @staticmethod
    @activity.defn
    async def get_global_tool_analytics() -> Dict[str, Any]:
        """Get aggregated tool usage analytics across all sessions"""
        try:
            analytics = await db_manager.get_global_tool_statistics()
            
            activity.logger.debug("Retrieved global tool analytics")
            return {
                "success": True,
                "analytics": analytics,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            activity.logger.error(f"Failed to get global tool analytics: {e}")
            return {
                "success": False,
                "error": str(e),
                "analytics": {},
                "timestamp": datetime.utcnow().isoformat()
            }

    @staticmethod
    @activity.defn
    async def save_conversation_turn_with_tool_analytics(session_id: str, turn_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save conversation turn and automatically update tool statistics if tool calls are present"""
        try:
            # First save the conversation turn
            saved_turn = await DatabaseActivities.save_conversation_turn(session_id, turn_data)
            
            # Extract tool calls from assistant responses for statistics
            tool_results = []
            for assistant_response in turn_data.get("assistant_responses", []):
                tool_calls = assistant_response.get("tool_calls", [])
                for tool_call in tool_calls:
                    # Convert tool call format to tool result format for statistics
                    tool_result = {
                        "tool_name": tool_call.get("tool_name", "unknown"),
                        "success": tool_call.get("success", False),
                        "status": tool_call.get("status", "unknown"),
                        "execution_time_seconds": tool_call.get("execution_time_ms", 0) / 1000.0,
                        "call_id": tool_call.get("tool_call_id"),
                        "timestamp": tool_call.get("timestamp")
                    }
                    tool_results.append(tool_result)
            
            # Update tool statistics if there are tool calls
            statistics_update = {"success": True, "statistics_summary": {"total_updated": 0}}
            if tool_results:
                statistics_update = await DatabaseActivities.update_tool_statistics_for_session(session_id, tool_results)
            
            activity.logger.info(f"Saved conversation turn {turn_data['turn_id']} with tool analytics for session {session_id}")
            return {
                "success": True,
                "saved_turn": saved_turn,
                "tool_statistics_update": statistics_update,
                "tool_calls_processed": len(tool_results),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            activity.logger.error(f"Failed to save conversation turn with tool analytics: {e}")
            raise


def build_conversation_turn(user_message: str, assistant_response: str, 
                          tool_calls: Optional[List[Dict[str, Any]]] = None,
                          mcp_calls: Optional[List[Dict[str, Any]]] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Helper function to build a complete conversation turn"""
    
    turn_id = f"turn_{str(uuid4())[:8]}"
    timestamp = datetime.utcnow().isoformat()
    
    # Build user message
    user_msg_id = f"msg_u_{str(uuid4())[:8]}"
    user_message_data = {
        "message_id": user_msg_id,
        "content": user_message,
        "timestamp": timestamp,
        "metadata": metadata.get("user_metadata", {}) if metadata else {}
    }
    
    # Build assistant response
    resp_id = f"resp_{str(uuid4())[:8]}"
    assistant_msg_id = f"msg_a_{str(uuid4())[:8]}"
    
    assistant_response_data = {
        "response_id": resp_id,
        "message_id": assistant_msg_id,
        "content": assistant_response,
        "timestamp": timestamp,
        "is_active": True,
        "tool_calls": tool_calls or [],
        "mcp_calls": mcp_calls or [],
        "final_content": assistant_response,
        "metadata": {
            "generation_type": "original",
            **(metadata.get("assistant_metadata", {}) if metadata else {})
        }
    }
    
    return {
        "turn_id": turn_id,
        "turn_number": 1,  # Will be set when saved
        "user_message": user_message_data,
        "assistant_responses": [assistant_response_data]
    }


def build_tool_call(tool_name: str, arguments: Dict[str, Any], 
                   result: Dict[str, Any], status: str = "completed",
                   execution_time_ms: int = 0) -> Dict[str, Any]:
    """Helper function to build a tool call entry"""
    
    return {
        "tool_call_id": f"call_{str(uuid4())[:8]}",
        "tool_name": tool_name,
        "arguments": arguments,
        "result": result,
        "status": status,
        "execution_time_ms": execution_time_ms,
        "timestamp": datetime.utcnow().isoformat()
    }


def build_enhanced_tool_call(tool_result: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to build an enhanced tool call entry from tool execution result"""
    
    return {
        "tool_call_id": tool_result.get("call_id", f"call_{str(uuid4())[:8]}"),
        "tool_name": tool_result.get("tool_name", "unknown"),
        "arguments": tool_result.get("arguments", {}),
        "result": tool_result.get("result"),
        "error": tool_result.get("error"),
        "status": tool_result.get("status", "unknown"),
        "success": tool_result.get("success", False),
        "execution_time_ms": tool_result.get("execution_time_ms", 0),
        "timestamp": tool_result.get("timestamp", datetime.utcnow().isoformat()),
        "metadata": tool_result.get("metadata", {})
    }


def build_conversation_turn_with_tools(user_message: str, assistant_response: str, 
                                     tool_results: Optional[List[Dict[str, Any]]] = None,
                                     mcp_calls: Optional[List[Dict[str, Any]]] = None,
                                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Enhanced helper function to build a complete conversation turn with tool calling support"""
    
    turn_id = f"turn_{str(uuid4())[:8]}"
    timestamp = datetime.utcnow().isoformat()
    
    # Build user message
    user_msg_id = f"msg_u_{str(uuid4())[:8]}"
    user_message_data = {
        "message_id": user_msg_id,
        "content": user_message,
        "timestamp": timestamp,
        "metadata": metadata.get("user_metadata", {}) if metadata else {}
    }
    
    # Build assistant response with enhanced tool call support
    resp_id = f"resp_{str(uuid4())[:8]}"
    assistant_msg_id = f"msg_a_{str(uuid4())[:8]}"
    
    # Process tool calls from tool results
    formatted_tool_calls = []
    if tool_results:
        for tool_result in tool_results:
            formatted_tool_call = build_enhanced_tool_call(tool_result)
            formatted_tool_calls.append(formatted_tool_call)
    
    # Calculate tool execution summary
    tool_execution_summary = {
        "total_tool_calls": len(formatted_tool_calls),
        "successful_tool_calls": len([tc for tc in formatted_tool_calls if tc.get("success", False)]),
        "failed_tool_calls": len([tc for tc in formatted_tool_calls if not tc.get("success", False)]),
        "total_execution_time_ms": sum(tc.get("execution_time_ms", 0) for tc in formatted_tool_calls),
        "tools_used": list(set(tc.get("tool_name", "unknown") for tc in formatted_tool_calls))
    }
    
    assistant_response_data = {
        "response_id": resp_id,
        "message_id": assistant_msg_id,
        "content": assistant_response,
        "timestamp": timestamp,
        "is_active": True,
        "tool_calls": formatted_tool_calls,
        "mcp_calls": mcp_calls or [],
        "final_content": assistant_response,
        "metadata": {
            "generation_type": "tool_enhanced" if formatted_tool_calls else "original",
            "tool_execution_summary": tool_execution_summary,
            **(metadata.get("assistant_metadata", {}) if metadata else {})
        }
    }
    
    return {
        "turn_id": turn_id,
        "turn_number": 1,  # Will be set when saved
        "user_message": user_message_data,
        "assistant_responses": [assistant_response_data],
        "metadata": {
            "has_tool_calls": len(formatted_tool_calls) > 0,
            "tool_execution_summary": tool_execution_summary,
            **(metadata.get("turn_metadata", {}) if metadata else {})
        }
    }


def build_mcp_call(server_name: str, tool_name: str, arguments: Dict[str, Any],
                  result: Dict[str, Any], status: str = "completed",
                  execution_time_ms: int = 0) -> Dict[str, Any]:
    """Helper function to build an MCP call entry"""
    
    return {
        "mcp_call_id": f"mcp_{str(uuid4())[:8]}",
        "server_name": server_name,
        "tool_name": tool_name,
        "arguments": arguments,
        "result": result,
        "status": status,
        "execution_time_ms": execution_time_ms,
        "timestamp": datetime.utcnow().isoformat()
    } 