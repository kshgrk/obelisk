"""
Database Activities for Temporal Workflows
These activities handle all database operations within Temporal workflows.
"""
import logging
from typing import Dict, Any, List, Optional

from temporalio import activity

from src.database.manager import db_manager, DatabaseError, SessionNotFoundError
from src.models.chat import ChatSessionCreate, ChatMessageCreate, MessageRole, SessionStatus

logger = logging.getLogger(__name__)


class DatabaseActivities:
    """Database activity implementations for Temporal workflows"""
    
    @staticmethod
    @activity.defn
    async def create_session(name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new chat session and return session ID"""
        try:
            session_data = ChatSessionCreate(name=name, metadata=metadata or {})
            session = await db_manager.create_session(session_data)
            
            activity.logger.info(f"Created session: {session.id}")
            return session.id
            
        except Exception as e:
            activity.logger.error(f"Failed to create session: {e}")
            raise
    
    @staticmethod
    @activity.defn
    async def add_message(session_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a message to a session"""
        try:
            # Handle string role values from workflow
            role_str = message_data["role"]
            if isinstance(role_str, str):
                message_role = MessageRole(role_str)
            else:
                message_role = role_str
                
            message_create = ChatMessageCreate(
                role=message_role,
                content=message_data["content"],
                metadata=message_data.get("metadata", {})
            )
            
            message = await db_manager.add_message(session_id, message_create)
            
            activity.logger.debug(f"Added message to session {session_id}")
            
            return {
                "id": message.id,
                "session_id": message.session_id,
                "role": message.role.value if hasattr(message.role, 'value') else str(message.role),
                "content": message.content,
                "metadata": message.metadata,
                "timestamp": message.timestamp.isoformat() if message.timestamp else None
            }
            
        except SessionNotFoundError:
            activity.logger.error(f"Session not found: {session_id}")
            raise
        except Exception as e:
            activity.logger.error(f"Failed to add message to session {session_id}: {e}")
            raise
    
    @staticmethod
    @activity.defn
    async def get_session_context(session_id: str, limit: int = 5) -> Dict[str, Any]:
        """Get recent messages from a session for context"""
        try:
            context = await db_manager.get_session_context(session_id, limit)
            
            messages = []
            for message in context.messages:
                messages.append({
                    "id": message.id,
                    "role": message.role.value if hasattr(message.role, 'value') else str(message.role),
                    "content": message.content,
                    "metadata": message.metadata,
                    "timestamp": message.timestamp.isoformat() if message.timestamp else None
                })
            
            activity.logger.debug(f"Retrieved {len(messages)} context messages for session {session_id}")
            
            # Return in the format expected by the workflow
            return {
                "messages": messages,
                "session_id": session_id,
                "total_messages": len(messages)
            }
            
        except SessionNotFoundError:
            activity.logger.error(f"Session not found: {session_id}")
            raise
        except Exception as e:
            activity.logger.error(f"Failed to get session context {session_id}: {e}")
            raise
    
    @staticmethod
    @activity.defn
    async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information"""
        try:
            session = await db_manager.get_session(session_id)
            
            if not session:
                return None
            
            return {
                "id": session.id,
                "name": session.name,
                "status": session.status.value,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "metadata": session.metadata,
                "message_count": session.message_count
            }
            
        except Exception as e:
            activity.logger.error(f"Failed to get session {session_id}: {e}")
            raise
    
    @staticmethod
    @activity.defn
    async def update_session_status(session_id: str, status: str) -> bool:
        """Update session status"""
        try:
            session_status = SessionStatus(status)
            updated = await db_manager.update_session_status(session_id, session_status)
            
            if updated:
                activity.logger.info(f"Updated session {session_id} status to {status}")
            else:
                activity.logger.warning(f"No session found to update: {session_id}")
            
            return updated
            
        except Exception as e:
            activity.logger.error(f"Failed to update session status {session_id}: {e}")
            raise
    
    @staticmethod
    @activity.defn
    async def session_exists(session_id: str) -> bool:
        """Check if a session exists"""
        try:
            exists = await db_manager.session_exists(session_id)
            return exists
            
        except Exception as e:
            activity.logger.error(f"Failed to check session existence {session_id}: {e}")
            return False
    
    @staticmethod
    @activity.defn
    async def get_session_history(session_id: str, offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """Get paginated session history"""
        try:
            messages = await db_manager.get_session_history(session_id, offset, limit)
            
            history = []
            for message in messages:
                history.append({
                    "id": message.id,
                    "role": message.role.value if hasattr(message.role, 'value') else str(message.role),
                    "content": message.content,
                    "metadata": message.metadata,
                    "timestamp": message.timestamp.isoformat() if message.timestamp else None
                })
            
            activity.logger.debug(f"Retrieved {len(history)} history messages for session {session_id}")
            return history
            
        except Exception as e:
            activity.logger.error(f"Failed to get session history {session_id}: {e}")
            raise
    
    @staticmethod
    @activity.defn
    async def list_sessions(status: Optional[str] = None, offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """List sessions with optional status filter"""
        try:
            session_status = SessionStatus(status) if status else None
            sessions = await db_manager.list_sessions(session_status, offset, limit)
            
            session_list = []
            for session in sessions:
                session_list.append({
                    "id": session.id,
                    "name": session.name,
                    "status": session.status.value,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                    "metadata": session.metadata,
                    "message_count": session.message_count
                })
            
            activity.logger.debug(f"Retrieved {len(session_list)} sessions")
            return session_list
            
        except Exception as e:
            activity.logger.error(f"Failed to list sessions: {e}")
            raise
    
    @staticmethod
    @activity.defn
    async def delete_session(session_id: str) -> bool:
        """Delete a session and all its messages"""
        try:
            deleted = await db_manager.delete_session(session_id)
            
            if deleted:
                activity.logger.info(f"Deleted session: {session_id}")
            else:
                activity.logger.warning(f"No session found to delete: {session_id}")
            
            return deleted
            
        except Exception as e:
            activity.logger.error(f"Failed to delete session {session_id}: {e}")
            raise 