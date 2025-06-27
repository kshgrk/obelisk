"""
Database manager for Obelisk Temporal Integration
Enhanced database operations with better error handling and model integration.
"""

import uuid
import aiosqlite
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from src.models.chat import (
    ChatSession, ChatMessage, ChatSessionCreate, ChatMessageCreate,
    MessageRole, SessionStatus, ChatContext
)
from src.config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base exception for database operations"""
    pass


class SessionNotFoundError(DatabaseError):
    """Raised when a session is not found"""
    pass


class DatabaseManager:
    """Enhanced database manager with model integration and better error handling"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.database.url.replace("sqlite:///", "")
        
    async def init_database(self) -> None:
        """Initialize the database with required tables and indexes"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Enable foreign key constraints
                await db.execute("PRAGMA foreign_keys = ON")
                
                # Create sessions table with enhanced fields
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT DEFAULT '{}',
                        message_count INTEGER DEFAULT 0
                    )
                """)
                
                # Create messages table with enhanced fields
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT DEFAULT '{}',
                        FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes for performance
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_messages_session_timestamp 
                    ON messages (session_id, timestamp DESC)
                """)
                
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_status 
                    ON sessions (status)
                """)
                
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sessions_updated 
                    ON sessions (updated_at DESC)
                """)
                
                await db.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise DatabaseError(f"Database initialization failed: {e}")
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager for database connections"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Enable foreign key constraints and row factory
                await db.execute("PRAGMA foreign_keys = ON")
                db.row_factory = aiosqlite.Row
                yield db
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise DatabaseError(f"Database connection failed: {e}")
    
    async def create_session(self, session_data: Optional[ChatSessionCreate] = None) -> ChatSession:
        """Create a new chat session and return the session object"""
        session_id = str(uuid.uuid4())
        name = session_data.name if session_data else None
        metadata = session_data.metadata if session_data else {}
        
        try:
            async with self.get_connection() as db:
                await db.execute(
                    """INSERT INTO sessions (id, name, metadata) VALUES (?, ?, ?)""",
                    (session_id, name, str(metadata))
                )
                await db.commit()
                
            logger.info(f"Created new session: {session_id}")
            
            return ChatSession(
                id=session_id,
                name=name,
                metadata=metadata,
                status=SessionStatus.ACTIVE,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                message_count=0
            )
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise DatabaseError(f"Session creation failed: {e}")
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get session information by ID"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(
                    """SELECT id, name, status, created_at, updated_at, metadata, message_count 
                       FROM sessions WHERE id = ?""",
                    (session_id,)
                )
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                return ChatSession(
                    id=row['id'],
                    name=row['name'],
                    status=SessionStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    metadata=eval(row['metadata']) if row['metadata'] else {},
                    message_count=row['message_count']
                )
                
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            raise DatabaseError(f"Failed to retrieve session: {e}")
    
    async def session_exists(self, session_id: str) -> bool:
        """Check if a session exists"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(
                    "SELECT 1 FROM sessions WHERE id = ? LIMIT 1",
                    (session_id,)
                )
                result = await cursor.fetchone()
                return result is not None
                
        except Exception as e:
            logger.error(f"Failed to check session existence {session_id}: {e}")
            return False
    
    async def add_message(self, session_id: str, message_data: ChatMessageCreate) -> ChatMessage:
        """Add a message to a session and update session timestamp"""
        try:
            async with self.get_connection() as db:
                # Verify session exists
                if not await self.session_exists(session_id):
                    raise SessionNotFoundError(f"Session {session_id} not found")
                
                # Insert message
                cursor = await db.execute(
                    """INSERT INTO messages (session_id, role, content, metadata) 
                       VALUES (?, ?, ?, ?)""",
                    (session_id, message_data.role.value, message_data.content, str(message_data.metadata))
                )
                message_id_raw = cursor.lastrowid
                if message_id_raw is None:
                    raise DatabaseError("Failed to get message ID after insertion")
                message_id = int(message_id_raw)
                
                # Update session timestamp and message count
                await db.execute(
                    """UPDATE sessions 
                       SET updated_at = CURRENT_TIMESTAMP, message_count = message_count + 1 
                       WHERE id = ?""",
                    (session_id,)
                )
                
                await db.commit()
                
                message = ChatMessage(
                    id=message_id,
                    session_id=session_id,
                    role=message_data.role,
                    content=message_data.content,
                    metadata=message_data.metadata,
                    timestamp=datetime.utcnow()
                )
                
                logger.debug(f"Added message to session {session_id}: {message_data.role.value}")
                return message
                
        except SessionNotFoundError:
            raise  
        except Exception as e:
            logger.error(f"Failed to add message to session {session_id}: {e}")
            raise DatabaseError(f"Failed to add message: {e}")
    
    async def get_session_context(self, session_id: str, limit: int | None = None) -> ChatContext:
        """Get recent messages from a session for context"""
        if limit is None:
            limit = settings.chat.max_context_messages
            
        try:
            async with self.get_connection() as db:
                # Get total message count
                cursor = await db.execute(
                    "SELECT message_count FROM sessions WHERE id = ?",
                    (session_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    raise SessionNotFoundError(f"Session {session_id} not found")
                
                total_messages = row['message_count']
                
                # Get recent messages
                cursor = await db.execute("""
                    SELECT id, role, content, timestamp, metadata FROM messages 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (session_id, limit))
                
                rows = await cursor.fetchall()
                
                # Reverse to get chronological order (oldest first)
                messages = []
                for row in reversed(list(rows)):
                    messages.append(ChatMessage(
                        id=row['id'],
                        session_id=session_id,
                        role=MessageRole(row['role']),
                        content=row['content'],
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        metadata=eval(row['metadata']) if row['metadata'] else {}
                    ))
                
                return ChatContext(
                    session_id=session_id,
                    messages=messages,
                    total_messages=total_messages,
                    context_window=limit
                )
                
        except SessionNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get session context {session_id}: {e}")
            raise DatabaseError(f"Failed to retrieve session context: {e}")
    
    async def get_session_history(self, session_id: str, offset: int = 0, limit: int = 50) -> List[ChatMessage]:
        """Get paginated session history"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute("""
                    SELECT id, role, content, timestamp, metadata FROM messages 
                    WHERE session_id = ? 
                    ORDER BY timestamp ASC 
                    LIMIT ? OFFSET ?
                """, (session_id, limit, offset))
                
                messages = []
                async for row in cursor:
                    messages.append(ChatMessage(
                        id=row['id'],
                        session_id=session_id,
                        role=MessageRole(row['role']),
                        content=row['content'],
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        metadata=eval(row['metadata']) if row['metadata'] else {}
                    ))
                
                return messages
                
        except Exception as e:
            logger.error(f"Failed to get session history {session_id}: {e}")
            raise DatabaseError(f"Failed to retrieve session history: {e}")
    
    async def list_sessions(self, status: Optional[SessionStatus] = None, 
                          offset: int = 0, limit: int = 50) -> List[ChatSession]:
        """List sessions with optional status filter"""
        try:
            async with self.get_connection() as db:
                if status:
                    cursor = await db.execute("""
                        SELECT id, name, status, created_at, updated_at, metadata, message_count 
                        FROM sessions 
                        WHERE status = ?
                        ORDER BY updated_at DESC 
                        LIMIT ? OFFSET ?
                    """, (status.value, limit, offset))
                else:
                    cursor = await db.execute("""
                        SELECT id, name, status, created_at, updated_at, metadata, message_count 
                        FROM sessions 
                        ORDER BY updated_at DESC 
                        LIMIT ? OFFSET ?
                    """, (limit, offset))
                
                sessions = []
                async for row in cursor:
                    sessions.append(ChatSession(
                        id=row['id'],
                        name=row['name'],
                        status=SessionStatus(row['status']),
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at']),
                        metadata=eval(row['metadata']) if row['metadata'] else {},
                        message_count=row['message_count']
                    ))
                
                return sessions
                
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            raise DatabaseError(f"Failed to list sessions: {e}")
    
    async def update_session_status(self, session_id: str, status: SessionStatus) -> bool:
        """Update session status"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(
                    """UPDATE sessions 
                       SET status = ?, updated_at = CURRENT_TIMESTAMP 
                       WHERE id = ?""",
                    (status.value, session_id)
                )
                await db.commit()
                
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to update session status {session_id}: {e}")
            raise DatabaseError(f"Failed to update session status: {e}")
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                await db.commit()
                
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"Deleted session: {session_id}")
                
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise DatabaseError(f"Failed to delete session: {e}")


# Global database manager instance
db_manager = DatabaseManager() 