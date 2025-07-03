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
from src.models.session_state import (
    SessionToolStateData, SessionConfiguration, ModelCapabilityInfo, 
    ToolAvailabilityInfo, ModelCapabilityLevel, SessionToolState,
    session_state_manager
)

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
            
            # Create models table for OpenRouter model management
            await db.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    is_tool_call BOOLEAN NOT NULL DEFAULT 0,
                    context_length INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                            "show_tool_calls": True,
                            "tools_enabled": True
                        },
                        "statistics": {
                            "total_tokens_input": 0,
                            "total_tokens_output": 0,
                            "last_response_time_ms": 0.0,
                            "average_response_time_ms": 0.0,
                            "total_response_time_ms": 0.0
                        },
                        "tool_statistics": {
                            "total_tool_calls": 0,
                            "successful_tool_calls": 0,
                            "failed_tool_calls": 0,
                            "cancelled_tool_calls": 0,
                            "total_tool_execution_time_ms": 0.0,
                            "average_tool_execution_time_ms": 0.0,
                            "tools_used": {},  # tool_name -> usage_count
                            "tool_success_rates": {},  # tool_name -> success_rate
                            "last_tool_call": None,  # timestamp of last tool call
                            "most_used_tool": None,
                            "fastest_tool": None,  # tool_name with fastest avg execution
                            "slowest_tool": None   # tool_name with slowest avg execution
                        },
                        "metadata": {
                            "total_messages": 0,
                            "total_turns": 0,
                            "features_used": ["chat"],
                            "last_updated": datetime.utcnow().isoformat(),
                            "supports_tool_calls": True,
                            "tool_calls_enabled": True
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

    async def update_tool_statistics(self, session_id: str, tool_name: str, execution_time: float, success: bool, cancelled: bool = False) -> None:
        """Update tool usage statistics for a session"""
        try:
            async with self.get_connection() as db:
                await db.execute("BEGIN")
                try:
                    # Get current session data
                    cursor = await db.execute(
                        "SELECT session_data FROM sessions WHERE session_id = ?",
                        (session_id,)
                    )
                    row = await cursor.fetchone()
                    
                    if not row:
                        raise ValueError(f"Session {session_id} not found")
                    
                    session_data = json.loads(row['session_data']) if row['session_data'] else {}
                    
                    # Ensure tool_statistics exists
                    if 'tool_statistics' not in session_data:
                        session_data['tool_statistics'] = {
                            "total_tool_calls": 0,
                            "successful_tool_calls": 0,
                            "failed_tool_calls": 0,
                            "cancelled_tool_calls": 0,
                            "total_tool_execution_time_ms": 0.0,
                            "average_tool_execution_time_ms": 0.0,
                            "tools_used": {},
                            "tool_success_rates": {},
                            "last_tool_call": None,
                            "most_used_tool": None,
                            "fastest_tool": None,
                            "slowest_tool": None
                        }
                    
                    stats = session_data['tool_statistics']
                    
                    # Update counters
                    stats['total_tool_calls'] += 1
                    if cancelled:
                        stats['cancelled_tool_calls'] += 1
                    elif success:
                        stats['successful_tool_calls'] += 1
                    else:
                        stats['failed_tool_calls'] += 1
                    
                    # Update execution time statistics
                    execution_time_ms = execution_time * 1000
                    stats['total_tool_execution_time_ms'] += execution_time_ms
                    stats['average_tool_execution_time_ms'] = (
                        stats['total_tool_execution_time_ms'] / stats['total_tool_calls']
                    )
                    
                    # Update tool-specific statistics
                    if tool_name not in stats['tools_used']:
                        stats['tools_used'][tool_name] = 0
                        stats['tool_success_rates'][tool_name] = {"total": 0, "successful": 0, "rate": 0.0}
                    
                    stats['tools_used'][tool_name] += 1
                    stats['tool_success_rates'][tool_name]["total"] += 1
                    if success and not cancelled:
                        stats['tool_success_rates'][tool_name]["successful"] += 1
                    
                    # Calculate success rate
                    tool_stats = stats['tool_success_rates'][tool_name]
                    tool_stats["rate"] = tool_stats["successful"] / tool_stats["total"] if tool_stats["total"] > 0 else 0.0
                    
                    # Update most used tool
                    most_used_count = 0
                    for t_name, count in stats['tools_used'].items():
                        if count > most_used_count:
                            most_used_count = count
                            stats['most_used_tool'] = t_name
                    
                    # Update timestamp
                    stats['last_tool_call'] = datetime.utcnow().isoformat()
                    
                    # Update metadata
                    session_data['metadata']['last_updated'] = datetime.utcnow().isoformat()
                    
                    # Save updated session data
                    await db.execute(
                        "UPDATE sessions SET session_data = ?, updated_at = ? WHERE session_id = ?",
                        (
                            json.dumps(session_data, sort_keys=False),
                            datetime.utcnow().isoformat(),
                            session_id
                        )
                    )
                    
                    await db.commit()
                    logger.info(f"Updated tool statistics for session {session_id}: {tool_name} ({'success' if success else 'failed' if not cancelled else 'cancelled'})")
                    
                except Exception:
                    await db.rollback()
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to update tool statistics: {e}")
            raise

    async def get_tool_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get tool usage statistics for a session"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(
                    "SELECT session_data FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                row = await cursor.fetchone()
                
                if not row:
                    return {}
                
                session_data = json.loads(row['session_data']) if row['session_data'] else {}
                return session_data.get('tool_statistics', {})
                
        except Exception as e:
            logger.error(f"Failed to get tool statistics: {e}")
            raise

    async def get_global_tool_statistics(self) -> Dict[str, Any]:
        """Get aggregated tool statistics across all sessions"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute("SELECT session_data FROM sessions WHERE session_data != '{}'")
                
                global_stats = {
                    "total_sessions_with_tools": 0,
                    "total_tool_calls": 0,
                    "successful_tool_calls": 0,
                    "failed_tool_calls": 0,
                    "cancelled_tool_calls": 0,
                    "tools_used": {},
                    "tool_success_rates": {},
                    "average_execution_time_ms": 0.0
                }
                
                total_execution_time = 0.0
                
                async for row in cursor:
                    session_data = json.loads(row['session_data']) if row['session_data'] else {}
                    tool_stats = session_data.get('tool_statistics', {})
                    
                    if tool_stats.get('total_tool_calls', 0) > 0:
                        global_stats['total_sessions_with_tools'] += 1
                        global_stats['total_tool_calls'] += tool_stats.get('total_tool_calls', 0)
                        global_stats['successful_tool_calls'] += tool_stats.get('successful_tool_calls', 0)
                        global_stats['failed_tool_calls'] += tool_stats.get('failed_tool_calls', 0)
                        global_stats['cancelled_tool_calls'] += tool_stats.get('cancelled_tool_calls', 0)
                        
                        total_execution_time += tool_stats.get('total_tool_execution_time_ms', 0.0)
                        
                        # Aggregate tool usage
                        for tool_name, count in tool_stats.get('tools_used', {}).items():
                            if tool_name not in global_stats['tools_used']:
                                global_stats['tools_used'][tool_name] = 0
                                global_stats['tool_success_rates'][tool_name] = {"total": 0, "successful": 0, "rate": 0.0}
                            
                            global_stats['tools_used'][tool_name] += count
                            
                            # Aggregate success rates
                            tool_success_data = tool_stats.get('tool_success_rates', {}).get(tool_name, {})
                            global_stats['tool_success_rates'][tool_name]["total"] += tool_success_data.get('total', 0)
                            global_stats['tool_success_rates'][tool_name]["successful"] += tool_success_data.get('successful', 0)
                
                # Calculate global success rates
                for tool_name, data in global_stats['tool_success_rates'].items():
                    data["rate"] = data["successful"] / data["total"] if data["total"] > 0 else 0.0
                
                # Calculate global average execution time
                if global_stats['total_tool_calls'] > 0:
                    global_stats['average_execution_time_ms'] = total_execution_time / global_stats['total_tool_calls']
                
                return global_stats
                
        except Exception as e:
            logger.error(f"Failed to get global tool statistics: {e}")
            raise

    async def save_models(self, models: List[dict]):
        """Save or update models in the database"""
        try:
            async with self.get_connection() as db:
                await db.execute("BEGIN")
                try:
                    # Clear existing models
                    await db.execute("DELETE FROM models")
                    
                    # Insert new models
                    for model in models:
                        await db.execute("""
                            INSERT INTO models (id, name, is_tool_call, context_length) 
                            VALUES (?, ?, ?, ?)
                        """, (
                            model['id'], 
                            model['name'], 
                            model.get('is_tool_call', False),
                            model.get('context_length', 0)
                        ))
                    
                    await db.commit()
                    logger.info(f"Saved {len(models)} models to database")
                    
                except Exception:
                    await db.rollback()
                    raise
                    
        except Exception as e:
            logger.error(f"Failed to save models: {e}")
            raise
    
    async def get_models(self, tools_only: bool = False) -> List[dict]:
        """Get all models, optionally filtered by tool call capability"""
        try:
            async with self.get_connection() as db:
                query = "SELECT id, name, is_tool_call, context_length FROM models"
                params = ()
                
                if tools_only:
                    query += " WHERE is_tool_call = 1"
                
                query += " ORDER BY name"
                
                cursor = await db.execute(query, params)
                rows = await cursor.fetchall()
                
                return [
                    {
                        "id": row['id'],
                        "name": row['name'], 
                        "is_tool_call": bool(row['is_tool_call']),
                        "context_length": row['context_length'] or 0
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            raise

    async def update_session_tool_state(self, session_id: str, tool_state: SessionToolStateData) -> bool:
        """Update session tool state in database"""
        try:
            async with self.get_connection() as db:
                # Get current session data
                cursor = await db.execute(
                    "SELECT session_data FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                row = await cursor.fetchone()
                
                if not row:
                    logger.warning(f"Session {session_id} not found for tool state update")
                    return False
                
                session_data = json.loads(row['session_data']) if row['session_data'] else {}
                
                # Update session state section
                session_data['session_state'] = {
                    "current_model": tool_state.current_model,
                    "model_capability_level": tool_state.model_info.capability_level.value,
                    "supports_tool_calls": tool_state.model_info.supports_tool_calls,
                    "available_tools": tool_state.get_available_tools(),
                    "session_configuration": {
                        "enable_tools": tool_state.session_config.enable_tools,
                        "max_concurrent_tools": tool_state.session_config.max_concurrent_tools,
                        "tool_timeout_seconds": tool_state.session_config.tool_timeout_seconds,
                        "cache_duration_minutes": tool_state.session_config.cache_duration_minutes,
                        "allowed_tools": list(tool_state.session_config.allowed_tools) if tool_state.session_config.allowed_tools else None,
                        "blocked_tools": list(tool_state.session_config.blocked_tools)
                    },
                    "model_switch_count": tool_state.model_switch_count,
                    "last_model_change": tool_state.last_model_change.isoformat() if tool_state.last_model_change else None,
                    "cache_statistics": {
                        "cache_hits": tool_state.cache_hits,
                        "cache_misses": tool_state.cache_misses,
                        "cache_refresh_count": tool_state.cache_refresh_count
                    },
                    "tool_availability": {
                        tool_name: {
                            "state": info.state.value,
                            "last_checked": info.last_checked.isoformat(),
                            "cache_expiry": info.cache_expiry.isoformat() if info.cache_expiry else None,
                            "error_message": info.error_message,
                            "execution_count": info.execution_count,
                            "success_count": info.success_count,
                            "average_execution_time_ms": info.average_execution_time_ms,
                            "last_execution_time": info.last_execution_time.isoformat() if info.last_execution_time else None
                        }
                        for tool_name, info in tool_state.tool_availability.items()
                    }
                }
                
                # Update database
                await db.execute(
                    "UPDATE sessions SET session_data = ?, updated_at = ? WHERE session_id = ?",
                    (json.dumps(session_data), datetime.utcnow().isoformat(), session_id)
                )
                await db.commit()
                
                logger.debug(f"Updated session tool state for {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update session tool state: {e}")
            return False

    async def load_session_tool_state(self, session_id: str) -> Optional[SessionToolStateData]:
        """Load session tool state from database"""
        try:
            async with self.get_connection() as db:
                cursor = await db.execute(
                    "SELECT session_data FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                session_data = json.loads(row['session_data']) if row['session_data'] else {}
                state_data = session_data.get('session_state', {})
                
                if not state_data.get('current_model'):
                    return None
                
                # Reconstruct model capability info
                model_info = ModelCapabilityInfo(
                    model_id=state_data['current_model'],
                    supports_tool_calls=state_data.get('supports_tool_calls', False),
                    capability_level=ModelCapabilityLevel(state_data.get('model_capability_level', 'none'))
                )
                
                # Reconstruct session configuration
                config_data = state_data.get('session_configuration', {})
                session_config = SessionConfiguration(
                    session_id=session_id,
                    enable_tools=config_data.get('enable_tools', True),
                    max_concurrent_tools=config_data.get('max_concurrent_tools', 3),
                    tool_timeout_seconds=config_data.get('tool_timeout_seconds', 30.0),
                    cache_duration_minutes=config_data.get('cache_duration_minutes', 30),
                    allowed_tools=set(config_data['allowed_tools']) if config_data.get('allowed_tools') else None,
                    blocked_tools=set(config_data.get('blocked_tools', []))
                )
                
                # Reconstruct tool availability info
                tool_availability = {}
                for tool_name, tool_data in state_data.get('tool_availability', {}).items():
                    tool_availability[tool_name] = ToolAvailabilityInfo(
                        tool_name=tool_name,
                        state=SessionToolState(tool_data['state']),
                        last_checked=datetime.fromisoformat(tool_data['last_checked']),
                        cache_expiry=datetime.fromisoformat(tool_data['cache_expiry']) if tool_data.get('cache_expiry') else None,
                        error_message=tool_data.get('error_message'),
                        execution_count=tool_data.get('execution_count', 0),
                        success_count=tool_data.get('success_count', 0),
                        average_execution_time_ms=tool_data.get('average_execution_time_ms', 0.0),
                        last_execution_time=datetime.fromisoformat(tool_data['last_execution_time']) if tool_data.get('last_execution_time') else None
                    )
                
                # Create session tool state
                cache_stats = state_data.get('cache_statistics', {})
                tool_state = SessionToolStateData(
                    session_id=session_id,
                    current_model=state_data['current_model'],
                    model_info=model_info,
                    tool_availability=tool_availability,
                    session_config=session_config,
                    last_model_change=datetime.fromisoformat(state_data['last_model_change']) if state_data.get('last_model_change') else None,
                    model_switch_count=state_data.get('model_switch_count', 0),
                    cache_refresh_count=cache_stats.get('cache_refresh_count', 0),
                    cache_hits=cache_stats.get('cache_hits', 0),
                    cache_misses=cache_stats.get('cache_misses', 0)
                )
                
                logger.debug(f"Loaded session tool state for {session_id}")
                return tool_state
                
        except Exception as e:
            logger.error(f"Failed to load session tool state: {e}")
            return None

    async def initialize_session_tool_state(self, session_id: str, model_id: str, model_info: ModelCapabilityInfo) -> Optional[SessionToolStateData]:
        """Initialize or load session tool state"""
        try:
            # Try to load existing state first
            existing_state = await self.load_session_tool_state(session_id)
            if existing_state:
                # Check if model changed
                if existing_state.current_model != model_id:
                    logger.info(f"Model changed for session {session_id}: {existing_state.current_model} → {model_id}")
                    # Update model in session state manager
                    updated_state = await session_state_manager.update_model_for_session(
                        session_id, model_id, model_info
                    )
                    if updated_state:
                        await self.update_session_tool_state(session_id, updated_state)
                        return updated_state
                else:
                    # Load into session state manager
                    await session_state_manager.create_session_state(
                        session_id, model_id, model_info, existing_state.session_config
                    )
                    return existing_state
            
            # Create new session state
            new_state = await session_state_manager.create_session_state(
                session_id, model_id, model_info
            )
            await self.update_session_tool_state(session_id, new_state)
            
            logger.info(f"Initialized session tool state for {session_id} with model {model_id}")
            return new_state
            
        except Exception as e:
            logger.error(f"Failed to initialize session tool state: {e}")
            return None

    async def get_session_tool_configuration(self, session_id: str) -> Optional[SessionConfiguration]:
        """Get session tool configuration"""
        try:
            tool_state = await self.load_session_tool_state(session_id)
            return tool_state.session_config if tool_state else None
        except Exception as e:
            logger.error(f"Failed to get session tool configuration: {e}")
            return None

    async def update_session_tool_configuration(self, session_id: str, config: SessionConfiguration) -> bool:
        """Update session tool configuration"""
        try:
            # Update in session state manager
            success = await session_state_manager.update_session_configuration(session_id, config)
            if not success:
                return False
            
            # Get updated state and save to database
            updated_state = await session_state_manager.get_session_state(session_id)
            if updated_state:
                await self.update_session_tool_state(session_id, updated_state)
                logger.info(f"Updated session tool configuration for {session_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update session tool configuration: {e}")
            return False

# Global instance
db_manager = DatabaseManager() 