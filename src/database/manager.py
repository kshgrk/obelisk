"""
Database manager for chat sessions and messages with optimized JSON structure
"""
import aiosqlite
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4
from contextlib import asynccontextmanager
from collections import OrderedDict

from src.config.settings import settings
from src.models.chat import ChatSession, ChatMessage, ChatSessionCreate, ChatMessageCreate, MessageRole, SessionStatus

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database manager with optimized conversation_turns JSON structure"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")
        
    async def initialize(self):
        """Initialize database with updated schema"""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON")
            
            # Create sessions table with optimized structure
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    name TEXT,
                    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'archived')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_data JSON DEFAULT '{}',
                    conversation_history JSON DEFAULT '{"conversation_turns": []}'
                )
            """)
            
            # Keep individual messages table for quick lookups and compatibility
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    turn_id TEXT,
                    role TEXT CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON DEFAULT '{}',
                    is_active BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            
            await db.commit()
            logger.info("Database initialized with optimized schema")

    @asynccontextmanager
    async def get_connection(self):
        """Get database connection with proper error handling"""
        conn = None
        try:
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        except Exception as e:
            if conn:
                await conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                await conn.close()

    async def create_session(self, session_data: ChatSessionCreate) -> ChatSession:
        """Create a new chat session with optimized structure"""
        session_id = str(uuid4())
        
        try:
            async with self.get_connection() as db:
                await db.execute("BEGIN")
                try:
                    # Initialize session data with proper structure matching examples
                    session_data_obj = {
                        "config": {
                            "model": "deepseek/deepseek-chat-v3-0324:free",
                            "temperature": 0.7,
                            "max_tokens": 1000,
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
                        "metadata": {
                            "total_messages": 0,
                            "total_turns": 0,
                            "features_used": ["chat"],
                            "last_updated": datetime.utcnow().isoformat()
                        }
                    }
                    
                    # Initialize conversation history
                    conversation_history = {
                        "conversation_turns": []
                    }
                    
                    now = datetime.utcnow().isoformat()
                    await db.execute(
                        """INSERT INTO sessions 
                           (session_id, name, status, created_at, updated_at, session_data, conversation_history)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            session_id,
                            session_data.name or f"Chat Session {session_id[:8]}",
                            "active",  # Default status since ChatSessionCreate doesn't have status
                            now,
                            now,
                            json.dumps(session_data_obj),
                            json.dumps(conversation_history)
                        )
                    )
                    
                    await db.commit()
                    logger.info(f"Created session {session_id}")
                    
                    return ChatSession(
                        id=session_id,
                        name=session_data.name or f"Chat Session {session_id[:8]}",
                        status=SessionStatus.ACTIVE,
                        created_at=datetime.fromisoformat(now.replace('Z', '+00:00')),
                        updated_at=datetime.fromisoformat(now.replace('Z', '+00:00')),
                        metadata=session_data_obj.get('metadata', {}),
                        message_count=0
                    )
                    
                except Exception:
                    await db.rollback()
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise

    async def add_conversation_turn(self, session_id: str, turn_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a complete conversation turn (user message + assistant response) atomically"""
        try:
            async with self.get_connection() as db:
                await db.execute("BEGIN")
                try:
                    # Get current conversation
                    cursor = await db.execute(
                        "SELECT conversation_history, session_data FROM sessions WHERE session_id = ?",
                        (session_id,)
                    )
                    row = await cursor.fetchone()
                    
                    if not row:
                        raise ValueError(f"Session {session_id} not found")
                    
                    # Parse current data
                    conversation = json.loads(row['conversation_history'])
                    session_data = json.loads(row['session_data']) if row['session_data'] else {}
                    
                    # Get metadata from session_data (with fallback structure)
                    metadata = session_data.get('metadata', {
                        'total_messages': 0,
                        'total_turns': 0,
                        'features_used': ['chat'],
                        'last_updated': datetime.utcnow().isoformat()
                    })
                    
                    # Set correct turn number and ensure proper field ordering
                    turn_number = len(conversation['conversation_turns']) + 1
                    
                    # Use OrderedDict for absolute field ordering control
                    ordered_turn = OrderedDict()
                    ordered_turn["turn_id"] = turn_data['turn_id']
                    ordered_turn["turn_number"] = turn_number
                    
                    # User message first (logical conversation flow)
                    user_msg = turn_data['user_message']
                    ordered_turn["user_message"] = OrderedDict()
                    ordered_turn["user_message"]["message_id"] = user_msg['message_id']
                    ordered_turn["user_message"]["content"] = user_msg['content']
                    ordered_turn["user_message"]["timestamp"] = user_msg['timestamp']
                    ordered_turn["user_message"]["metadata"] = user_msg.get('metadata', {})
                    
                    # Assistant responses second
                    ordered_turn["assistant_responses"] = []
                    for resp in turn_data['assistant_responses']:
                        ordered_resp = OrderedDict()
                        ordered_resp["response_id"] = resp['response_id']
                        ordered_resp["message_id"] = resp['message_id'] 
                        ordered_resp["content"] = resp['content']
                        ordered_resp["final_content"] = resp.get('final_content', resp['content'])
                        ordered_resp["timestamp"] = resp['timestamp']
                        ordered_resp["is_active"] = resp.get('is_active', True)
                        ordered_resp["tool_calls"] = resp.get('tool_calls', [])
                        ordered_resp["mcp_calls"] = resp.get('mcp_calls', [])
                        ordered_resp["metadata"] = resp.get('metadata', {})
                        ordered_turn["assistant_responses"].append(ordered_resp)
                    
                    # Add new turn with proper ordering
                    conversation['conversation_turns'].append(ordered_turn)
                    
                    # Update metadata statistics
                    metadata['total_turns'] = len(conversation['conversation_turns'])
                    metadata['total_messages'] = sum(
                        1 + len(turn.get('assistant_responses', [])) 
                        for turn in conversation['conversation_turns']
                    )
                    metadata['last_updated'] = datetime.utcnow().isoformat()
                    
                    # Update session_data with new metadata
                    session_data['metadata'] = metadata
                    
                    # Update session (JSON-only storage with preserved ordering)
                    await db.execute(
                        """UPDATE sessions 
                           SET conversation_history = ?, session_data = ?, updated_at = ?
                           WHERE session_id = ?""",
                        (
                            json.dumps(conversation, sort_keys=False),
                            json.dumps(session_data, sort_keys=False),
                            datetime.utcnow().isoformat(),
                            session_id
                        )
                    )
                    
                    await db.commit()
                    logger.info(f"Added conversation turn to session {session_id}")
                    return turn_data
                    
                except Exception:
                    await db.rollback()
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to add conversation turn: {e}")
            raise

    # Legacy compatibility method removed - using pure JSON storage only
    # async def _store_individual_messages(self, db, session_id: str, turn_data: Dict[str, Any]):
    #     """Store individual messages for quick lookups - DISABLED for pure JSON approach"""
    #     pass

    async def get_conversation_history(self, session_id: str) -> Dict[str, Any]:
        """Get full conversation history for a session"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(
                    "SELECT conversation_history FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                row = await cursor.fetchone()
                
                if not row:
                    return {"conversation_turns": []}
                
                return json.loads(row['conversation_history'])
                
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get session information by ID"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(
                    """SELECT session_id, name, status, created_at, updated_at, 
                              session_data, conversation_history 
                       FROM sessions WHERE session_id = ?""",
                    (session_id,)
                )
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                # Safe datetime parsing
                created_at = None
                updated_at = None
                
                if row['created_at']:
                    try:
                        created_at = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        created_at = datetime.utcnow()
                
                if row['updated_at']:
                    try:
                        updated_at = datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        updated_at = datetime.utcnow()
                
                # Parse session data and get metadata
                session_data = json.loads(row['session_data']) if row['session_data'] else {}
                metadata = session_data.get('metadata', {})
                conversation = json.loads(row['conversation_history']) if row['conversation_history'] else {"conversation_turns": []}
                message_count = metadata.get('total_messages', 0)
                
                return ChatSession(
                    id=row['session_id'],
                    name=row['name'],
                    status=SessionStatus(row['status']),
                    created_at=created_at,
                    updated_at=updated_at,
                    metadata=metadata,
                    message_count=message_count
                )
                
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            raise

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> List[ChatSession]:
        """List sessions with pagination"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(
                    """SELECT session_id, name, status, created_at, updated_at, session_data
                       FROM sessions 
                       ORDER BY updated_at DESC 
                       LIMIT ? OFFSET ?""",
                    (limit, offset)
                )
                
                sessions = []
                async for row in cursor:
                    # Safe datetime parsing
                    created_at = None
                    updated_at = None
                    
                    if row['created_at']:
                        try:
                            created_at = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            created_at = datetime.utcnow()
                    
                    if row['updated_at']:
                        try:
                            updated_at = datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            updated_at = datetime.utcnow()
                    
                    # Parse session data and get metadata
                    session_data = json.loads(row['session_data']) if row['session_data'] else {}
                    metadata = session_data.get('metadata', {})
                    
                    sessions.append(ChatSession(
                        id=row['session_id'],
                        name=row['name'],
                        status=SessionStatus(row['status']),
                        created_at=created_at,
                        updated_at=updated_at,
                        metadata=metadata,
                        message_count=metadata.get('total_messages', 0)
                    ))
                
                return sessions
                
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            raise

    # Legacy compatibility method - DISABLED for pure JSON conversation_turns approach
    async def add_message(self, session_id: str, message_data: ChatMessageCreate) -> ChatMessage:
        """
        Legacy method - DISABLED. 
        Use add_conversation_turn() for complete conversation turns in pure JSON storage.
        """
        raise NotImplementedError(
            "Legacy add_message() disabled. Use add_conversation_turn() for complete conversation turns."
        )

    async def get_session_context(self, session_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get recent conversation context for AI processing"""
        try:
            conversation = await self.get_conversation_history(session_id)
            turns = conversation.get('conversation_turns', [])
            
            # Get last N turns
            recent_turns = turns[-limit:] if len(turns) > limit else turns
            
            # Format for AI context
            context_messages = []
            for turn in recent_turns:
                # Add user message
                user_msg = turn['user_message']
                context_messages.append({
                    "role": "user",
                    "content": user_msg['content'],
                    "message_id": user_msg['message_id']
                })
                
                # Add active assistant response
                for response in turn.get('assistant_responses', []):
                    if response.get('is_active', True):
                        context_messages.append({
                            "role": "assistant", 
                            "content": response.get('final_content', response.get('content', '')),
                            "message_id": response['message_id']
                        })
                        break  # Only one active response per turn
            
            return {
                "session_id": session_id,
                "messages": context_messages,
                "total_turns": len(turns),
                "context_turns": len(recent_turns)
            }
            
        except Exception as e:
            logger.error(f"Failed to get session context: {e}")
            raise

# Global instance
db_manager = DatabaseManager() 