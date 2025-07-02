"""
Session management API routes for Obelisk chat application
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime
import logging
import json

from src.database.manager import DatabaseManager, db_manager
from src.models.chat import (
    ChatSession, 
    SessionListResponse,
    SessionHistoryResponse,
    ChatSessionCreate
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])

class SessionNameUpdate(BaseModel):
    name: str

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
    plus the full session data (config, statistics, metadata) in the optimized JSON format
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
        
        # Get the full session data from database directly
        async with db.get_connection() as connection:
            cursor = await connection.execute(
                "SELECT session_data FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()
            
            if row and row['session_data']:
                session_data = json.loads(row['session_data'])
            else:
                session_data = {
                    "statistics": {
                        "total_tokens_input": 0,
                        "total_tokens_output": 0,
                        "last_response_time_ms": 0.0,
                        "average_response_time_ms": 0.0,
                        "total_response_time_ms": 0.0
                    },
                    "metadata": session.metadata
                }
        
        # Extract the latest config from the most recent conversation turn
        latest_config = {
            "model": "deepseek/deepseek-chat-v3-0324:free",
            "temperature": 1.0,
            "max_tokens": 5000,
            "streaming": True,
            "show_tool_calls": True
        }
        
        # Look for the most recent generation_config in conversation history
        generation_config = {}  # Initialize the variable
        if conversation_history and conversation_history.get("conversation_turns"):
            turns = conversation_history["conversation_turns"]
            # Search from most recent turn backwards
            for turn in reversed(turns):
                assistant_responses = turn.get("assistant_responses", [])
                for response in assistant_responses:
                    if response.get("is_active", True):
                        metadata = response.get("metadata", {})
                        found_config = metadata.get("generation_config", {})
                        if found_config:
                            # Found a generation config, use it as the latest
                            generation_config = found_config
                            latest_config.update(generation_config)
                            break
                if generation_config:  # Break outer loop if we found config
                    break
        
        # Set the config in session_data
        session_data["config"] = latest_config
        
        # Return combined session info and conversation history
        return {
            "session_id": session.id,
            "name": session.name,
            "status": session.status,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "message_count": session.message_count,
            "session_data": session_data,
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
            # Update the session name to be a more friendly format
            session_name = f"Chat Session {session.id[:8]}"
            
            # Update the session in the database with the new name
            async with db.get_connection() as connection:
                await connection.execute(
                    "UPDATE sessions SET name = ?, updated_at = ? WHERE session_id = ?",
                    (session_name, datetime.utcnow().isoformat(), session.id)
                )
                await connection.commit()
            
            # Update the returned session object
            session.name = session_name
            
        return session
        
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to create session: {str(e)}"
        )

# Removed redundant get_session_context endpoint - use GET /sessions/{id} instead


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Delete a session and all its conversation history"""
    try:
        # Check if session exists
        async with db.get_connection() as connection:
            cursor = await connection.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Delete messages first (due to foreign key constraint)
            await connection.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (session_id,)
            )
            
            # Delete the session
            await connection.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            
            await connection.commit()
            
        logger.info(f"Deleted session {session_id}")
        return {"message": "Session deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{session_id}/name")
async def update_session_name(
    session_id: str,
    name_update: SessionNameUpdate,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Update the name of a session"""
    try:
        # Check if session exists and get current data
        async with db.get_connection() as connection:
            cursor = await connection.execute(
                "SELECT session_data FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Parse existing session data or create new structure
            if row['session_data']:
                session_data = json.loads(row['session_data'])
            else:
                session_data = {
                    "config": {
                        "model": "deepseek/deepseek-chat-v3-0324:free",
                        "temperature": 1.0,
                        "max_tokens": 5000,
                        "streaming": True,
                        "show_tool_calls": True
                    },
                    "statistics": {
                        "total_tokens_input": 0,
                        "total_tokens_output": 0,
                        "last_response_time_ms": 0.0,
                        "average_response_time_ms": 0.0,
                        "total_response_time_ms": 0.0
                    },
                    "metadata": {}
                }
            
            # Ensure metadata section exists
            if "metadata" not in session_data:
                session_data["metadata"] = {}
            
            # Update the session name in metadata
            session_data["metadata"]["name"] = name_update.name
            
            # Update both the main session name field AND the session_data
            await connection.execute(
                "UPDATE sessions SET name = ?, session_data = ?, updated_at = ? WHERE session_id = ?",
                (name_update.name, json.dumps(session_data), datetime.utcnow().isoformat(), session_id)
            )
            
            await connection.commit()
            
        logger.info(f"Updated session {session_id} name to: {name_update.name}")
        return {"message": "Session name updated successfully", "name": name_update.name}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session name for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") 