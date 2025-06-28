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
                    # Get current metadata
                    cursor = await db.execute(
                        "SELECT session_metadata FROM sessions WHERE session_id = ?",
                        (session_id,)
                    )
                    row = await cursor.fetchone()
                    
                    if not row:
                        return False
                    
                    # Update metadata
                    current_metadata = json.loads(row['session_metadata'])
                    current_metadata.update(metadata_updates)
                    current_metadata['last_updated'] = datetime.utcnow().isoformat()
                    
                    # Save updated metadata
                    await db.execute(
                        "UPDATE sessions SET session_metadata = ?, updated_at = ? WHERE session_id = ?",
                        (json.dumps(current_metadata), datetime.utcnow().isoformat(), session_id)
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