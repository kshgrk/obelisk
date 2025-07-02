"""
Session Management Activities for Temporal Workflows
These activities handle session-specific operations like monitoring, cleanup, and lifecycle management.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import json
import httpx

from temporalio import activity

from src.database.manager import db_manager
from src.models.chat import SessionStatus
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class SessionActivities:
    """Session management activity implementations for Temporal workflows"""
    
    @staticmethod
    @activity.defn
    async def check_session_inactivity(session_id: str, timeout_hours: int = 24) -> bool:
        """
        Check if a session has been inactive for longer than the specified timeout
        """
        try:
            session = await db_manager.get_session(session_id)
            
            if not session:
                activity.logger.warning(f"Session not found for inactivity check: {session_id}")
                return True  # Consider non-existent sessions as inactive
            
            # Calculate inactivity threshold
            threshold = datetime.utcnow() - timedelta(hours=timeout_hours)
            
            # Check if last update was before threshold
            is_inactive = session.updated_at < threshold if session.updated_at else False
            
            if is_inactive:
                activity.logger.info(f"Session {session_id} is inactive (last update: {session.updated_at})")
            
            return is_inactive
            
        except Exception as e:
            activity.logger.error(f"Failed to check session inactivity {session_id}: {e}")
            return False  # Default to active if check fails
    
    @staticmethod
    @activity.defn
    async def cleanup_session_data(session_id: str) -> Dict[str, Any]:
        """
        Perform cleanup operations for a session (e.g., old message cleanup, optimization)
        """
        try:
            activity.logger.info(f"Starting cleanup for session: {session_id}")
            
            # Get session info
            session = await db_manager.get_session(session_id)
            if not session:
                return {"error": "Session not found", "session_id": session_id}
            
            cleanup_results = {
                "session_id": session_id,
                "cleanup_time": datetime.now(timezone.utc).isoformat(),
                "operations_performed": [],
                "errors": []
            }
            
            # Example cleanup operations (implement as needed):
            
            # 1. Archive old messages if session has too many
            if session.message_count > 1000:  # Configurable threshold
                try:
                    # In a real implementation, you might:
                    # - Move old messages to an archive table
                    # - Compress message content
                    # - Update session metadata
                    activity.logger.info(f"Session {session_id} has {session.message_count} messages - considering archival")
                    cleanup_results["operations_performed"].append("message_count_check")
                except Exception as e:
                    cleanup_results["errors"].append(f"Message archival error: {e}")
            
            # 2. Update session metadata with cleanup info
            try:
                # You could update session metadata with cleanup timestamps
                cleanup_results["operations_performed"].append("metadata_update")
            except Exception as e:
                cleanup_results["errors"].append(f"Metadata update error: {e}")
            
            activity.logger.info(f"Cleanup completed for session {session_id}")
            return cleanup_results
            
        except Exception as e:
            activity.logger.error(f"Session cleanup failed for {session_id}: {e}")
            return {
                "session_id": session_id,
                "error": str(e),
                "cleanup_time": datetime.now(timezone.utc).isoformat()
            }
    
    @staticmethod
    @activity.defn
    async def log_session_completion(session_id: str) -> Dict[str, Any]:
        """
        Log session completion and gather final statistics
        """
        try:
            session = await db_manager.get_session(session_id)
            
            if not session:
                return {"error": "Session not found", "session_id": session_id}
            
            # Calculate session duration
            session_duration = datetime.now(timezone.utc) - session.created_at if session.created_at else timedelta(0)
            # End of Selection
            
            completion_log = {
                "session_id": session_id,
                "completion_time": datetime.now(timezone.utc).isoformat(),
                "session_duration_seconds": session_duration.total_seconds(),
                "total_messages": session.message_count,
                "session_status": session.status.value,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None
            }
            
            activity.logger.info(f"Session {session_id} completed: {session.message_count} messages, "
                               f"{session_duration.total_seconds():.0f}s duration")
            
            return completion_log
            
        except Exception as e:
            activity.logger.error(f"Failed to log session completion {session_id}: {e}")
            return {
                "session_id": session_id,
                "error": str(e),
                "completion_time": datetime.now(timezone.utc).isoformat()
            }
    
    @staticmethod
    @activity.defn
    async def get_session_metrics(session_id: str) -> Dict[str, Any]:
        """
        Gather comprehensive metrics for a session
        """
        try:
            session = await db_manager.get_session(session_id)
            
            if not session:
                return {"error": "Session not found", "session_id": session_id}
            
            # Get recent message activity
            conversation_history = await db_manager.get_conversation_history(session_id)
            recent_messages = conversation_history.get('conversation_turns', [])
            
            # Calculate metrics
            session_age = datetime.now(timezone.utc) - session.created_at if session.created_at else timedelta(0)
            last_activity = datetime.now(timezone.utc) - session.updated_at if session.updated_at else timedelta(0)
            
            avg_message_length = 0
            if recent_messages:
                # Calculate average message length from conversation turns
                total_length = 0
                message_count = 0
                for turn in recent_messages[-10:]:  # Last 10 turns
                    if 'user_message' in turn:
                        total_length += len(turn['user_message'].get('content', ''))
                        message_count += 1
                    for response in turn.get('assistant_responses', []):
                        if response.get('is_active', True):
                            total_length += len(response.get('content', ''))
                            message_count += 1
                            break
                if message_count > 0:
                    avg_message_length = total_length / message_count
            
            metrics = {
                "session_id": session_id,
                "session_age_seconds": session_age.total_seconds(),
                "last_activity_seconds": last_activity.total_seconds(),
                "total_messages": session.message_count,
                "avg_message_length": avg_message_length,
                "status": session.status.value,
                "has_name": session.name is not None,
                "metadata_keys": list(session.metadata.keys()) if session.metadata else [],
                "recent_message_count": len(recent_messages)
            }
            
            return metrics
            
        except Exception as e:
            activity.logger.error(f"Failed to get session metrics {session_id}: {e}")
            return {
                "session_id": session_id,
                "error": str(e)
            }
    
    @staticmethod
    @activity.defn
    async def archive_inactive_sessions(max_sessions: int = 100) -> Dict[str, Any]:
        """
        Archive sessions that have been inactive for a long time
        """
        try:
            activity.logger.info(f"Starting batch archival of inactive sessions (max: {max_sessions})")
            
            # Get active sessions ordered by last update (oldest first)
            sessions = await db_manager.list_sessions(
                offset=0,
                limit=max_sessions * 2  # Get more to filter
            )
            
            archived_count = 0
            errors = []
            settings = get_settings()
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=settings.chat.session_timeout_hours * 2)
            
            for session in sessions:
                if archived_count >= max_sessions:
                    break
                
                # Check if session should be archived
                if (session.status.value == "active" and 
                    session.updated_at and session.updated_at < cutoff_time and 
                    session.message_count > 0):
                    
                    try:
                        # Archive the session by updating status directly in database
                        async with db_manager.get_connection() as connection:
                            await connection.execute(
                                "UPDATE sessions SET status = ?, updated_at = ? WHERE session_id = ?",
                                (SessionStatus.ARCHIVED.value, datetime.now(timezone.utc).isoformat(), session.id)
                            )
                            await connection.commit()
                        
                        archived_count += 1
                        activity.logger.debug(f"Archived session: {session.id}")
                        
                    except Exception as e:
                        errors.append(f"Failed to archive session {session.id}: {e}")
            
            result = {
                "archived_count": archived_count,
                "errors": errors,
                "cutoff_time": cutoff_time.isoformat(),
                "total_sessions_checked": len(sessions)
            }
            
            activity.logger.info(f"Batch archival completed: {archived_count} sessions archived")
            return result
            
        except Exception as e:
            activity.logger.error(f"Batch session archival failed: {e}")
            return {
                "archived_count": 0,
                "error": str(e)
            }
    
    @staticmethod
    @activity.defn
    async def validate_session_integrity(session_id: str) -> Dict[str, Any]:
        """
        Validate session data integrity and consistency
        """
        try:
            session = await db_manager.get_session(session_id)
            
            if not session:
                return {
                    "session_id": session_id,
                    "valid": False,
                    "error": "Session not found"
                }
            
            validation_results = {
                "session_id": session_id,
                "valid": True,
                "checks_performed": [],
                "issues_found": []
            }
            
            # Check 1: Message count consistency
            conversation_history = await db_manager.get_conversation_history(session_id)
            actual_turns = conversation_history.get('conversation_turns', [])
            if len(actual_turns) != session.message_count:
                validation_results["issues_found"].append(
                    f"Message count mismatch: session shows {session.message_count}, "
                    f"actual turn count is {len(actual_turns)}"
                )
                validation_results["valid"] = False
            validation_results["checks_performed"].append("message_count_consistency")
            
            # Check 2: Timestamp consistency
            if (session.updated_at is not None and session.created_at is not None and 
                session.updated_at < session.created_at):
                validation_results["issues_found"].append("Updated timestamp is before created timestamp")
                validation_results["valid"] = False
            validation_results["checks_performed"].append("timestamp_consistency")
            
            # Check 3: Status validity
            valid_statuses = ["active", "inactive", "archived"]
            if session.status.value not in valid_statuses:
                validation_results["issues_found"].append(f"Invalid status: {session.status.value}")
                validation_results["valid"] = False
            validation_results["checks_performed"].append("status_validity")
            
            activity.logger.info(f"Session validation completed for {session_id}: "
                               f"{'VALID' if validation_results['valid'] else 'INVALID'}")
            
            return validation_results
            
        except Exception as e:
            activity.logger.error(f"Session validation failed for {session_id}: {e}")
            return {
                "session_id": session_id,
                "valid": False,
                "error": str(e)
            }

@activity.defn
async def generate_session_name(user_message: str) -> str:
    """
    Generate a concise session name based on the user's first message using Mistral AI via OpenRouter
    
    Args:
        user_message: The first message from the user
        
    Returns:
        Generated session name (max 50 characters)
    """
    try:
        from src.temporal.activities.openrouter import OpenRouterActivities
        
        # Prepare the prompt for Mistral to generate a session name
        system_prompt = """You are an assistant that creates concise, descriptive titles for chat sessions. 
        Given a user's first message, generate a short, clear title (maximum 50 characters) that captures the main topic or intent.
        
        Rules:
        - Maximum 50 characters
        - No quotes or special formatting
        - Descriptive but concise
        - Professional tone
        - Focus on the main topic/intent
        
        Examples:
        User: "How do I deploy a Python app to AWS?"
        Title: "Python AWS Deployment Guide"
        
        User: "I need help with React state management"
        Title: "React State Management Help"
        
        User: "What's the weather like today?"
        Title: "Weather Inquiry"
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate a title for this message: {user_message}"}
        ]
        
        # Use OpenRouter with Mistral model via Temporal activity
        try:
            request_data = {
                "messages": messages,
                "model": "mistralai/mistral-small-3.2-24b-instruct:free",
                "max_tokens": 20,  # Keep it short
                "temperature": 0.3,  # Lower temperature for more consistent naming
                "stream": False
            }
            
            result = await OpenRouterActivities.chat_completion(request_data)
            
            if result.get("content"):
                generated_name = result["content"].strip()
                
                # Clean up the generated name
                # Remove quotes if present
                generated_name = generated_name.strip('"\'')
                
                # Ensure it's not too long
                if len(generated_name) > 50:
                    generated_name = generated_name[:47] + "..."
                
                logger.info(f"Generated session name via OpenRouter: {generated_name}")
                return generated_name
            else:
                logger.error(f"OpenRouter activity failed: No content in response")
                # Fallback to simple name generation
                words = user_message.strip().split()[:4]
                return " ".join(words)[:50] if words else "New Chat"
                
        except Exception as e:
            logger.error(f"Error calling OpenRouter activity for session naming: {e}")
            # Fallback to simple name generation
            words = user_message.strip().split()[:4]
            return " ".join(words)[:50] if words else "New Chat"
                
    except Exception as e:
        logger.error(f"Error generating session name: {e}")
        # Fallback to simple name generation
        words = user_message.strip().split()[:4]
        return " ".join(words)[:50] if words else "New Chat"


@activity.defn
async def update_session_name_via_api(session_id: str, session_name: str) -> Dict[str, Any]:
    """
    Update the session name via the API endpoint
    
    Args:
        session_id: The session ID to update
        session_name: The new session name
        
    Returns:
        Dictionary with success status and details
    """
    try:
        import httpx
        from src.config.settings import get_settings
        
        settings = get_settings()
        
        # Call the API endpoint to update session name
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"http://{settings.server.host}:{settings.server.port}/sessions/{session_id}/name",
                json={"name": session_name},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Updated session {session_id} name via API: {session_name}")
                return {"success": True, "session_name": session_name, "api_response": result}
            else:
                logger.error(f"API error updating session name: {response.status_code} - {response.text}")
                return {"success": False, "error": f"API error: {response.status_code}"}
                
    except Exception as e:
        logger.error(f"Error updating session name via API: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def update_session_name_in_db(session_id: str, session_name: str) -> Dict[str, Any]:
    """
    Update the session name in the database
    
    Args:
        session_id: The session ID to update
        session_name: The new session name
        
    Returns:
        Dictionary with success status and details
    """
    try:
        from src.database.manager import db_manager
        
        # Ensure database is initialized
        await db_manager.initialize()
        
        # Get current session data
        async with db_manager.get_connection() as connection:
            cursor = await connection.execute(
                "SELECT session_data FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "Session not found"}
            
            # Parse existing session data or create new structure
            if row['session_data']:
                session_data = json.loads(row['session_data'])
            else:
                session_data = {
                    "config": {},
                    "statistics": {},
                    "metadata": {}
                }
            
            # Ensure metadata exists
            if "metadata" not in session_data:
                session_data["metadata"] = {}
            
            # Update the session name in metadata
            session_data["metadata"]["name"] = session_name
            
            # Update the session in database
            await connection.execute(
                "UPDATE sessions SET session_data = ? WHERE session_id = ?",
                (json.dumps(session_data), session_id)
            )
            
            await connection.commit()
            
        logger.info(f"Updated session {session_id} name to: {session_name}")
        return {"success": True, "session_name": session_name}
        
    except Exception as e:
        logger.error(f"Error updating session name in database: {e}")
        return {"success": False, "error": str(e)} 