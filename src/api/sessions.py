"""
Session management API routes for Obelisk chat application
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime
import logging

from src.database.manager import DatabaseManager, db_manager
from src.models.chat import (
    ChatSession, 
    SessionListResponse,
    SessionHistoryResponse,
    ChatSessionCreate
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])

async def get_db_manager() -> DatabaseManager:
    """Dependency to get database manager instance"""
    # Ensure database is initialized
    await db_manager.initialize()
    return db_manager

@router.get("", response_model=SessionListResponse)
async def get_all_sessions(
    limit: int = Query(50, ge=1, le=100, description="Number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    db: DatabaseManager = Depends(get_db_manager)
) -> SessionListResponse:
    """
    Get all session names and basic information
    
    Returns a list of sessions with their names, IDs, status, and basic metadata
    """
    try:
        sessions = await db.list_sessions(limit=limit, offset=offset)
        
        # Get total count for pagination
        # Note: This is a simplified approach; you might want to optimize this
        # by adding a count method to the database manager
        all_sessions = await db.list_sessions(limit=1000, offset=0)  # Get a large number to count
        total = len(all_sessions)
        
        return SessionListResponse(
            sessions=sessions,
            total=total,
            page=offset // limit + 1,
            page_size=limit
        )
        
    except Exception as e:
        logger.error(f"Failed to get sessions: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve sessions: {str(e)}"
        )

@router.get("/{session_id}", response_model=dict)
async def get_session_conversation_history(
    session_id: str,
    db: DatabaseManager = Depends(get_db_manager)
) -> dict:
    """
    Get full conversation history for a specific session
    
    Returns the complete conversation history including all turns and messages
    in the optimized JSON format from the database
    """
    try:
        # First check if session exists
        session = await db.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404, 
                detail=f"Session {session_id} not found"
            )
        
        # Get the full conversation history
        conversation_history = await db.get_conversation_history(session_id)
        
        # Return combined session info and conversation history
        return {
            "session_id": session.id,
            "name": session.name,
            "status": session.status,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "message_count": session.message_count,
            "metadata": session.metadata,
            "conversation_history": conversation_history
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation history for session {session_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve conversation history: {str(e)}"
        )

# Removed redundant get_session_name endpoint - use GET /sessions/{id} instead

@router.post("", response_model=ChatSession)
async def create_new_session(
    session_data: Optional[ChatSessionCreate] = None,
    db: DatabaseManager = Depends(get_db_manager)
) -> ChatSession:
    """
    Create a new chat session
    Session name is optional - if not provided, session ID will be used as name
    """
    try:
        # If no session data provided, create with empty name
        if session_data is None:
            session_data = ChatSessionCreate()
        
        # Create the session first to get the ID
        session = await db.create_session(session_data)
        
        # If no name was provided, update the session to use ID as name
        if not session_data.name:
            # Update the session name to be the session ID
            session.name = session.id
            
        return session
        
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to create session: {str(e)}"
        )

# Removed redundant get_session_context endpoint - use GET /sessions/{id} instead 