"""
Obelisk Chat Frontend Application
"""

from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import json
from datetime import datetime
import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

# Import the event system
import sys
import os

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import backend API router for Cloud Run compatibility
try:
    from src.api.router import api_router
    BACKEND_AVAILABLE = True
except ImportError:
    logger.warning("Backend API router not available - running in frontend-only mode")
    BACKEND_AVAILABLE = False

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown"""
    # Startup
    logger.info("Starting Obelisk Frontend")

    # Initialize backend if available
    if BACKEND_AVAILABLE:
        try:
            from src.database.manager import db_manager
            await db_manager.initialize()
            logger.info("Backend database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize backend: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Obelisk Frontend")

app = FastAPI(title="Obelisk Frontend", lifespan=lifespan)

# Include backend API router if available
if BACKEND_AVAILABLE:
    app.include_router(api_router, prefix="/api", tags=["backend"])

# Backend API base URL (fallback for external calls if needed)
BACKEND_URL = "http://127.0.0.1:8001"

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Setup templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Events endpoints removed - using direct streaming from /chat endpoint

@app.get("/sessions")
async def get_sessions():
    """Fetch sessions from backend database"""
    if BACKEND_AVAILABLE:
        try:
            from src.database.manager import db_manager
            await db_manager.initialize()
            sessions = await db_manager.list_sessions(limit=50, offset=0)

            # Format sessions for frontend compatibility
            formatted_sessions = []
            for session in sessions:
                formatted_sessions.append({
                    "id": session.id,
                    "name": session.name or f"Session {session.id[:8]}",
                    "status": "active",  # Default status
                    "created_at": session.created_at.isoformat() if hasattr(session.created_at, 'isoformat') else str(session.created_at),
                    "updated_at": session.updated_at.isoformat() if hasattr(session.updated_at, 'isoformat') else str(session.updated_at),
                    "metadata": {
                        "total_messages": 0,  # Will be updated when we implement message counting
                        "total_turns": 0,
                        "model": "unknown",
                        "settings": {
                            "temperature": 0.7,
                            "max_tokens": 1000,
                            "streaming": True
                        },
                        "statistics": {
                            "last_response_time_ms": 0,
                            "total_tokens_input": 0,
                            "total_tokens_output": 0
                        },
                        "features_used": ["chat"],
                        "user_preferences": {
                            "streaming": True,
                            "show_tool_calls": True
                        },
                        "last_updated": session.updated_at.isoformat() if hasattr(session.updated_at, 'isoformat') else str(session.updated_at)
                    },
                    "message_count": 0
                })

            return {"sessions": formatted_sessions}

        except Exception as e:
            print(f"Error fetching sessions from local backend: {e}")
            # Fall through to mock data

    # Fallback to mock data matching the expected API structure
    return JSONResponse({
        "sessions": [
            {
                "id": "mock_session_1",
                "name": "Mock Chat Session",
                "status": "active",
                "created_at": "2025-06-28T13:33:00.779657",
                "updated_at": "2025-06-28T13:34:09.617610",
                "metadata": {
                    "total_messages": 2,
                    "total_turns": 1,
                    "model": "mock/model",
                    "settings": {
                        "temperature": 0.7,
                        "max_tokens": 1000,
                        "streaming": True
                    },
                    "statistics": {
                        "last_response_time_ms": 0,
                        "total_tokens_input": 50,
                        "total_tokens_output": 100
                    },
                    "features_used": ["chat"],
                    "user_preferences": {
                        "streaming": True,
                        "show_tool_calls": True
                    },
                    "last_updated": "2025-06-28T13:34:09.617592"
                },
                "message_count": 2
            }
        ]
    })

@app.get("/sessions/{session_id}")
async def get_session_detail(session_id: str):
    """Fetch detailed session data using integrated backend"""
    if BACKEND_AVAILABLE:
        try:
            from src.api.sessions import get_session_by_id
            result = await get_session_by_id(session_id)
            return result
        except Exception as e:
            print(f"Error fetching session {session_id} from local backend: {e}")
            # Fall through to mock data

    # Fallback for unknown sessions - match the expected API structure
    return JSONResponse({
        "session_id": session_id,
        "name": f"Mock Session {session_id[:8]}",
        "status": "active",
        "created_at": "2025-06-28T13:33:00.779657",
        "updated_at": "2025-06-28T13:34:09.617610",
        "message_count": 2,
        "metadata": {
            "total_messages": 2,
            "total_turns": 1,
            "model": "mock/model",
            "settings": {
                "temperature": 0.7,
                "max_tokens": 1000,
                "streaming": True
            },
            "statistics": {
                "last_response_time_ms": 0,
                "total_tokens_input": 50,
                "total_tokens_output": 100
            },
            "features_used": ["chat"],
            "user_preferences": {
                "streaming": True,
                "show_tool_calls": True
            },
            "last_updated": "2025-06-28T13:34:09.617592"
        },
        "conversation_history": {
            "conversation_turns": [
                {
                    "turn_id": "turn_mock1",
                    "turn_number": 1,
                    "user_message": {
                        "message_id": "msg_u_mock1",
                        "content": "Hello, this is a test message",
                        "timestamp": "2025-06-28T13:33:34.344567+00:00",
                        "metadata": {
                            "source": "frontend_test",
                            "streaming": True
                        }
                    },
                    "assistant_responses": [
                        {
                            "response_id": "resp_mock1",
                            "message_id": "msg_a_mock1",
                            "content": "Hello! I'm a mock response for testing the frontend. This session is not connected to the real backend.",
                            "final_content": "Hello! I'm a mock response for testing the frontend. This session is not connected to the real backend.",
                            "timestamp": "2025-06-28T13:33:34.344567+00:00",
                            "is_active": True,
                            "tool_calls": [],
                            "mcp_calls": [],
                            "metadata": {
                                "finish_reason": "stop",
                                "generation_type": "original",
                                "model": "mock/model",
                                "response_time_ms": 0,
                                "streaming": True,
                                "tokens_input": 50,
                                "tokens_output": 100
                            }
                        }
                    ]
                }
            ]
        }
    })

def format_timestamp(timestamp_str):
    """Format timestamp for display"""
    if not timestamp_str:
        return "Just now"
    
    try:
        # Handle format like "2025-06-28 14:49:42"
        if " " in timestamp_str and ":" in timestamp_str:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%I:%M %p")
        # Handle ISO format
        elif "T" in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            return dt.strftime("%I:%M %p")
        else:
            return timestamp_str
    except Exception:
        return timestamp_str

@app.post("/api/sessions")
async def create_session(request: Request):
    """Handle session creation using integrated backend"""
    if not BACKEND_AVAILABLE:
        return JSONResponse({
            "error": "Backend not available - running in frontend-only mode"
        }, status_code=503)

    try:
        body = await request.json()
        from src.api.sessions import create_session as backend_create_session
        from pydantic import BaseModel

        # Create a ChatSessionCreate object
        class ChatSessionCreate(BaseModel):
            name: str = None

        session_data = ChatSessionCreate(**body)
        result = await backend_create_session(session_data)
        return result

    except Exception as e:
        print(f"Error creating session: {e}")
        return JSONResponse({"error": "Failed to create session"}, status_code=500)

@app.post("/api/chat")
async def send_message(request: Request):
    """Handle chat messages using integrated backend API"""
    if not BACKEND_AVAILABLE:
        return JSONResponse({
            "error": "Backend not available - running in frontend-only mode"
        }, status_code=503)

    try:
        body = await request.json()
        print(f"Frontend received chat request: {body}")

        # Extract data from frontend request
        message_content = body.get("message", "")
        session_id = body.get("session_id")
        stream = body.get("stream", False)
        config_override = body.get("config_override")  # Extract config_override

        if not session_id:
            return JSONResponse({"error": "session_id is required"}, status_code=400)

        if not message_content.strip():
            return JSONResponse({"error": "message cannot be empty"}, status_code=400)

        # Use the integrated backend API instead of proxying
        try:
            from src.api.chat import simple_chat
            from pydantic import BaseModel

            # Create a SimpleChatRequest object
            class SimpleChatRequest(BaseModel):
                session_id: str
                message: str
                model_id: str = None
                stream: bool = True
                config_override: dict = None

            chat_request = SimpleChatRequest(
                session_id=session_id,
                message=message_content,
                stream=stream,
                config_override=config_override
            )

            # Call the simple_chat function directly
            result = await simple_chat(chat_request)

            # Return the result as-is since simple_chat handles formatting
            return result

        except Exception as chat_error:
            print(f"Error calling chat endpoint: {chat_error}")
            return JSONResponse({
                "error": f"Chat processing failed: {str(chat_error)}"
            }, status_code=500)

    except Exception as e:
        print(f"Error in send_message: {e}")
        return JSONResponse({
            "error": f"Failed to send message: {str(e)}"
        }, status_code=500)

@app.post("/api/chat/completions")
async def chat_completions(request: Request):
    """Handle OpenAI-compatible completions using integrated backend"""
    if not BACKEND_AVAILABLE:
        return JSONResponse({
            "error": "Backend not available - running in frontend-only mode"
        }, status_code=503)

    try:
        body = await request.json()
        from src.api.chat import chat_completions as backend_chat_completions
        from pydantic import BaseModel

        # Create a ChatCompletionRequest object
        class ChatCompletionRequest(BaseModel):
            model: str = None
            messages: list
            stream: bool = False
            max_tokens: int = None
            temperature: float = None

        completion_request = ChatCompletionRequest(**body)
        result = await backend_chat_completions(completion_request)
        return result

    except Exception as e:
        print(f"Error with chat completions: {e}")
        return JSONResponse({"error": "Failed to process completion"}, status_code=500)

@app.post("/api/models/refresh")
async def refresh_models():
    """Handle models refresh using integrated backend"""
    if not BACKEND_AVAILABLE:
        return JSONResponse({
            "error": "Backend not available - running in frontend-only mode"
        }, status_code=503)

    try:
        # Import the refresh_models function directly
        from src.api.router import refresh_models as backend_refresh_models

        # Call the backend function directly
        result = await backend_refresh_models()
        return result

    except Exception as e:
        print(f"Error refreshing models: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/models")
async def get_models(tools_only: bool = False):
    """Handle models retrieval using integrated backend"""
    if not BACKEND_AVAILABLE:
        return JSONResponse({
            "error": "Backend not available - running in frontend-only mode",
            "models": [],
            "count": 0
        }, status_code=503)

    try:
        # Import the get_models function directly
        from src.api.router import get_models as backend_get_models

        # Call the backend function directly
        result = await backend_get_models(tools_only=tools_only)
        return result

    except Exception as e:
        print(f"Error getting models: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health():
    return {"status": "healthy", "frontend": "with_backend_integration"}

if __name__ == "__main__":
    import uvicorn
    import os
    # Use PORT environment variable for Cloud Run compatibility (defaults to 8080 for Cloud Run)
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port) 