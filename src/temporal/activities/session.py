"""
Session Management Activities for Temporal Workflows
These activities handle session-specific operations like monitoring, cleanup, and lifecycle management.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from temporalio import activity

from src.database.manager import db_manager
from src.models.chat import SessionStatus
from src.config.settings import settings

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
            is_inactive = session.updated_at < threshold
            
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
                "cleanup_time": datetime.utcnow().isoformat(),
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
                "cleanup_time": datetime.utcnow().isoformat()
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
            session_duration = datetime.utcnow() - session.created_at
            
            completion_log = {
                "session_id": session_id,
                "completion_time": datetime.utcnow().isoformat(),
                "session_duration_seconds": session_duration.total_seconds(),
                "total_messages": session.message_count,
                "session_status": session.status.value,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat()
            }
            
            activity.logger.info(f"Session {session_id} completed: {session.message_count} messages, "
                               f"{session_duration.total_seconds():.0f}s duration")
            
            return completion_log
            
        except Exception as e:
            activity.logger.error(f"Failed to log session completion {session_id}: {e}")
            return {
                "session_id": session_id,
                "error": str(e),
                "completion_time": datetime.utcnow().isoformat()
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
            recent_messages = await db_manager.get_session_history(session_id, offset=0, limit=10)
            
            # Calculate metrics
            session_age = datetime.utcnow() - session.created_at
            last_activity = datetime.utcnow() - session.updated_at
            
            avg_message_length = 0
            if recent_messages:
                total_length = sum(len(msg.content) for msg in recent_messages)
                avg_message_length = total_length / len(recent_messages)
            
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
                status=None,  # Get all sessions
                offset=0,
                limit=max_sessions * 2  # Get more to filter
            )
            
            archived_count = 0
            errors = []
            cutoff_time = datetime.utcnow() - timedelta(hours=settings.chat.session_timeout_hours * 2)
            
            for session in sessions:
                if archived_count >= max_sessions:
                    break
                
                # Check if session should be archived
                if (session.status.value == "active" and 
                    session.updated_at < cutoff_time and 
                    session.message_count > 0):
                    
                    try:
                        # Archive the session
                        await db_manager.update_session_status(session.id, SessionStatus.ARCHIVED)
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
            actual_messages = await db_manager.get_session_history(session_id, offset=0, limit=10000)
            if len(actual_messages) != session.message_count:
                validation_results["issues_found"].append(
                    f"Message count mismatch: session shows {session.message_count}, "
                    f"actual count is {len(actual_messages)}"
                )
                validation_results["valid"] = False
            validation_results["checks_performed"].append("message_count_consistency")
            
            # Check 2: Timestamp consistency
            if session.updated_at < session.created_at:
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