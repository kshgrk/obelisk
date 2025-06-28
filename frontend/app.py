"""
Obelisk Chat Frontend Application
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import json

app = FastAPI(title="Obelisk Frontend")

# Backend API base URL
BACKEND_URL = "http://localhost:8001"

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/sessions")
async def get_sessions():
    """Fetch sessions from backend database"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/sessions")
            if response.status_code == 200:
                # Return the sessions data in the expected format
                return response.json()
    except Exception as e:
        print(f"Error fetching sessions from backend: {e}")
    
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
    """Fetch detailed session data with conversation history"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/sessions/{session_id}")
            if response.status_code == 200:
                # Return the session data in the expected format
                return response.json()
    except Exception as e:
        print(f"Error fetching session {session_id} from backend: {e}")
    
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
        from datetime import datetime
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

@app.get("/health")
async def health():
    return {"status": "healthy", "frontend": "with_backend_integration"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000) 