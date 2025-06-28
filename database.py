"""
Database module for Obelisk chat sessions
Handles SQLite operations for storing and retrieving chat sessions and messages.
"""

import uuid
import aiosqlite
from typing import List, Optional


# Database configuration
DATABASE_PATH = "chat_sessions.db"


class DatabaseManager:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    async def init_database(self):
        """Initialize the database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Create sessions table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create messages table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                )
            """)
            
            # Create index for faster queries
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_timestamp 
                ON messages (session_id, timestamp DESC)
            """)
            
            await db.commit()
    
    async def create_session(self) -> str:
        """Create a new chat session and return its UUID"""
        session_id = str(uuid.uuid4())
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO sessions (session_id) VALUES (?)",
                (session_id,)
            )
            await db.commit()
        
        return session_id
    
    async def get_session_history(self, session_id: str, limit: int = 5) -> List[dict]:
        """Get the last N messages from a session for context"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT role, content, timestamp FROM messages 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (session_id, limit))
            
            rows = await cursor.fetchall()
            
            # Reverse to get chronological order (oldest first)
            messages = []
            for row in reversed(list(rows)):
                messages.append({
                    "role": row[0],
                    "content": row[1],
                    "timestamp": row[2]
                })
            
            return messages
    
    async def add_message(self, session_id: str, role: str, content: str):
        """Add a message to a session and update session timestamp"""
        async with aiosqlite.connect(self.db_path) as db:
            # Add the message
            await db.execute(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )
            
            # Update session timestamp
            await db.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                (session_id,)
            )
            
            await db.commit()
    
    async def session_exists(self, session_id: str) -> bool:
        """Check if a session exists"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM sessions WHERE session_id = ? LIMIT 1",
                (session_id,)
            )
            result = await cursor.fetchone()
            return result is not None
    
    async def get_session_info(self, session_id: str) -> Optional[dict]:
        """Get session information with full message history"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get session info
            session_cursor = await db.execute(
                "SELECT session_id, created_at, updated_at FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            session_data = await session_cursor.fetchone()
            
            if not session_data:
                return None
            
            # Get all messages
            messages_cursor = await db.execute("""
                SELECT role, content, timestamp FROM messages 
                WHERE session_id = ? 
                ORDER BY timestamp ASC
            """, (session_id,))
            
            messages = []
            async for row in messages_cursor:
                messages.append({
                    "role": row[0],
                    "content": row[1],
                    "timestamp": row[2]
                })
            
            return {
                "session_id": session_data[0],
                "created_at": session_data[1],
                "updated_at": session_data[2],
                "messages": messages
            } 