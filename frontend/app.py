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

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Event system removed - using direct streaming from /chat endpoint

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown"""
    # Startup
    logger.info("Starting Obelisk Frontend")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Obelisk Frontend")

app = FastAPI(title="Obelisk Frontend", lifespan=lifespan)

# Backend API base URL
BACKEND_URL = "http://localhost:8001"

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Events endpoints removed - using direct streaming from /chat endpoint

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
    """Proxy session creation to backend"""
    try:
        body = await request.json()
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BACKEND_URL}/sessions", json=body)
            
            # Check if response is successful
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    print(f"Session created successfully: {response_data}")
                    return response_data
                except Exception as json_error:
                    print(f"Error parsing session response JSON: {json_error}")
                    print(f"Response content: {response.text}")
                    return JSONResponse({"error": "Invalid response from backend"}, status_code=500)
            else:
                print(f"Backend returned error {response.status_code}: {response.text}")
                return JSONResponse({"error": f"Backend error: {response.status_code}"}, status_code=response.status_code)
                
    except Exception as e:
        print(f"Error creating session: {e}")
        return JSONResponse({"error": "Failed to create session"}, status_code=500)

@app.post("/api/chat")
async def send_message(request: Request):
    """Proxy chat messages to backend using the /chat endpoint with conversation history"""
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
        
        # Create request for backend /chat endpoint
        chat_request = {
            "session_id": session_id,
            "message": message_content,
            "stream": stream
        }
        
        # Add config_override if provided
        if config_override:
            chat_request["config_override"] = config_override
        
        # Add timeout to prevent hanging
        timeout = httpx.Timeout(60.0)  # Increased to 60s for chat workflows
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            print(f"Forwarding to: {BACKEND_URL}/chat")
            response = await client.post(f"{BACKEND_URL}/chat", json=chat_request)
            print(f"Backend response status: {response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text
                print(f"Backend error response: {error_text}")
                return JSONResponse({
                    "error": f"Backend error: {error_text}",
                    "status_code": response.status_code
                }, status_code=response.status_code)
            
            # Handle streaming vs non-streaming responses
            if stream:
                # For streaming responses, we need to collect all the chunks
                full_content = ""
                content_type = response.headers.get("content-type", "")
                
                if "text/plain" in content_type:  # Streaming response
                    response_text = response.text
                    
                    # Parse the SSE streaming data to extract content
                    lines = response_text.split('\n')
                    for line in lines:
                        if line.startswith('data: ') and not line.endswith('[DONE]'):
                            try:
                                chunk_data = json.loads(line[6:])  # Remove 'data: '
                                if 'content' in chunk_data:
                                    full_content += chunk_data['content']
                            except json.JSONDecodeError:
                                continue
                    
                    response_content = full_content
                else:
                    # Try to parse as JSON
                    try:
                        result = response.json()
                        response_content = result.get("response", result.get("content", "No response received"))
                    except json.JSONDecodeError:
                        response_content = response.text
            else:
                # Non-streaming response
                try:
                    result = response.json()
                    response_content = result.get("response", result.get("content", "No response received"))
                except json.JSONDecodeError:
                    response_content = response.text
            
            print(f"Processed response content: {response_content[:100]}...")
            
            # Get the actual model used from config_override or check backend response
            actual_model = "unknown"
            if config_override and config_override.get("model"):
                actual_model = config_override["model"]
            else:
                # Try to get from backend response if available
                try:
                    backend_result = response.json()
                    actual_model = backend_result.get("model", "unknown")
                except:
                    actual_model = "unknown"
            
            print(f"Using model in response: {actual_model}")
            
            # Return in OpenRouter-compatible format for frontend consistency
            return {
                "id": f"chatcmpl-{session_id[-8:]}",
                "object": "chat.completion",
                "created": int(datetime.now().timestamp()),
                "model": actual_model,  # Use actual model instead of hardcoded
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_content
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": len(message_content.split()),
                    "completion_tokens": len(response_content.split()),
                    "total_tokens": len(message_content.split()) + len(response_content.split())
                }
            }
            
    except httpx.TimeoutException:
        print("Request timed out")
        return JSONResponse({
            "error": "Request timed out. Please try again.",
            "timeout": True
        }, status_code=504)
    except Exception as e:
        print(f"Error in send_message: {e}")
        return JSONResponse({
            "error": f"Failed to send message: {str(e)}"
        }, status_code=500)

@app.post("/api/chat/completions")
async def chat_completions(request: Request):
    """Proxy OpenAI-compatible completions to backend"""
    try:
        body = await request.json()
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BACKEND_URL}/chat/completions", json=body)
            return response.json()
    except Exception as e:
        print(f"Error with chat completions: {e}")
        return JSONResponse({"error": "Failed to process completion"}, status_code=500)

@app.post("/api/models/refresh")
async def refresh_models():
    """Proxy to backend models refresh endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BACKEND_URL}/models/refresh")
            return response.json()
    except Exception as e:
        print(f"Error refreshing models: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/models")
async def get_models(tools_only: bool = False):
    """Proxy to backend models get endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/models", params={"tools_only": tools_only})
            return response.json()
    except Exception as e:
        print(f"Error getting models: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# API Key Management Endpoints
@app.post("/api/api-key/test")
async def test_api_key(request: Request):
    """Proxy to backend API key test endpoint"""
    try:
        body = await request.json()
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BACKEND_URL}/api-key/test", json=body)
            return response.json()
    except Exception as e:
        print(f"Error testing API key: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/api-key/update")
async def update_api_key(request: Request):
    """Proxy to backend API key update endpoint"""
    try:
        body = await request.json()
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BACKEND_URL}/api-key/update", json=body)
            return response.json()
    except Exception as e:
        print(f"Error updating API key: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/api-key/current")
async def get_current_api_key():
    """Proxy to backend API key current status endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/api-key/current")
            return response.json()
    except Exception as e:
        print(f"Error getting current API key: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/settings/refresh")
async def refresh_settings():
    """Proxy to backend settings refresh endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BACKEND_URL}/settings/refresh")
            return response.json()
    except Exception as e:
        print(f"Error refreshing settings: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health():
    return {"status": "healthy", "frontend": "with_backend_integration"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000) 