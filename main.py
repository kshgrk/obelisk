import os
import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator, Optional, List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import database manager
from database import DatabaseManager

app = FastAPI(title="Obelisk - OpenRouter FastAPI Server", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await db_manager.init_database()

# OpenRouter configuration
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
MODEL_NAME = "deepseek/deepseek-chat-v3-0324:free"

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    stream: bool = True
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000

class SessionChatRequest(BaseModel):
    session_id: str
    message: str
    stream: bool = True
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000

class SessionCreateResponse(BaseModel):
    session_id: str
    created_at: str

class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[dict]
    created_at: str
    updated_at: str

# Global database manager instance
db_manager = DatabaseManager()

async def stream_openrouter_response(messages: list[dict], temperature: Optional[float], max_tokens: Optional[int], session_id: Optional[str] = None, user_message: Optional[str] = None) -> AsyncGenerator[str, None]:
    """Stream responses from OpenRouter API"""
    
    # Get API key from environment
    api_key = os.getenv("OPENROUTER_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_KEY not found in environment variables")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8001",
        "X-Title": "Obelisk FastAPI Server"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": True,
        "temperature": temperature or 0.7,
        "max_tokens": max_tokens or 1000
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{OPENROUTER_API_BASE}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status_code != 200:
                    response_text = await response.aread()
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"OpenRouter API error: {response_text.decode()}"
                    )
                
                # Store the complete response for database saving
                complete_response = ""
                
                async for chunk in response.aiter_lines():
                    if chunk.startswith("data: "):
                        data = chunk[6:]  # Remove "data: " prefix
                        
                        if data.strip() == "[DONE]":
                            break
                            
                        try:
                            chunk_data = json.loads(data)
                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                delta = chunk_data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    complete_response += delta["content"]
                                    yield f"data: {json.dumps(chunk_data)}\n\n"
                        except json.JSONDecodeError:
                            continue
                
                # Save messages to database if session_id is provided
                if session_id and user_message and complete_response.strip():
                    await db_manager.add_message(session_id, "user", user_message)
                    await db_manager.add_message(session_id, "assistant", complete_response.strip())
                            
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Request to OpenRouter API timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error communicating with OpenRouter API: {str(e)}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Obelisk FastAPI Server is running!", "model": MODEL_NAME}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "model": MODEL_NAME}

@app.post("/sessions", response_model=SessionCreateResponse)
async def create_session():
    """Create a new chat session and return session ID"""
    session_id = await db_manager.create_session()
    return SessionCreateResponse(
        session_id=session_id,
        created_at=datetime.now().isoformat()
    )

@app.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str):
    """Get the history of a specific chat session"""
    session_info = await db_manager.get_session_info(session_id)
    
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionHistoryResponse(
        session_id=session_info["session_id"],
        messages=session_info["messages"],
        created_at=session_info["created_at"],
        updated_at=session_info["updated_at"]
    )

@app.post("/chat/completions")
async def chat_completions(request: ChatRequest):
    """Chat completions endpoint with streaming support"""
    
    # Convert Pydantic models to dictionaries
    messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    
    if request.stream:
        # Return streaming response
        return StreamingResponse(
            stream_openrouter_response(messages, request.temperature, request.max_tokens),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
    else:
        # Return non-streaming response
        api_key = os.getenv("OPENROUTER_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENROUTER_KEY not found in environment variables")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8001",
            "X-Title": "Obelisk FastAPI Server"
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "stream": False,
            "temperature": request.temperature or 0.7,
            "max_tokens": request.max_tokens or 1000
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{OPENROUTER_API_BASE}/chat/completions",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"OpenRouter API error: {response.text}"
                    )
                
                return response.json()
                
            except httpx.TimeoutException:
                raise HTTPException(status_code=504, detail="Request to OpenRouter API timed out")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error communicating with OpenRouter API: {str(e)}")

@app.post("/chat")
async def simple_chat(request: dict):
    """Simplified chat endpoint that accepts a message string"""
    
    message = request.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Create a simple chat request
    chat_request = ChatRequest(
        messages=[ChatMessage(role="user", content=message)],
        stream=request.get("stream", True),
        temperature=request.get("temperature", 0.7),
        max_tokens=request.get("max_tokens", 1000)
    )
    
    return await chat_completions(chat_request)

@app.post("/sessions/{session_id}/chat")
async def session_chat(session_id: str, request: dict):
    """Session-based chat with context from previous messages"""
    
    # Validate session exists
    if not await db_manager.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    message = request.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Get previous context (last 5 messages)
    previous_messages = await db_manager.get_session_history(session_id, limit=5)
    
    # Build context messages for OpenRouter API
    context_messages = []
    
    # Add previous messages for context (excluding timestamps for API)
    for msg in previous_messages:
        context_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add current user message
    context_messages.append({
        "role": "user",
        "content": message
    })
    
    # Create enhanced chat request with context
    stream = request.get("stream", True)
    temperature = request.get("temperature", 0.7)
    max_tokens = request.get("max_tokens", 1000)
    
    if stream:
        # Return streaming response with session context
        return StreamingResponse(
            stream_openrouter_response(
                context_messages, 
                temperature, 
                max_tokens, 
                session_id=session_id, 
                user_message=message
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
    else:
        # Handle non-streaming response with session context
        api_key = os.getenv("OPENROUTER_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENROUTER_KEY not found in environment variables")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8001",
            "X-Title": "Obelisk FastAPI Server"
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": context_messages,
            "stream": False,
            "temperature": temperature or 0.7,
            "max_tokens": max_tokens or 1000
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{OPENROUTER_API_BASE}/chat/completions",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"OpenRouter API error: {response.text}"
                    )
                
                response_data = response.json()
                
                # Save messages to database
                if "choices" in response_data and len(response_data["choices"]) > 0:
                    assistant_content = response_data["choices"][0]["message"]["content"]
                    await db_manager.add_message(session_id, "user", message)
                    await db_manager.add_message(session_id, "assistant", assistant_content)
                
                return response_data
                
            except httpx.TimeoutException:
                raise HTTPException(status_code=504, detail="Request to OpenRouter API timed out")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error communicating with OpenRouter API: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
