"""
Main API router for Obelisk chat application
Aggregates all API routes and provides a single import point
"""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from .sessions import router as sessions_router
from .chat import router as chat_router
import logging
import asyncio
import json
from collections import defaultdict, deque
from typing import Dict, List
import time
import httpx
import os
from src.database.manager import db_manager

# Create main API router
api_router = APIRouter()

# Include all sub-routers
api_router.include_router(sessions_router)
api_router.include_router(chat_router)

logger = logging.getLogger(__name__)

# In-memory event storage for real-time streaming
# In production, you'd use Redis or similar
session_events: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
active_streams: Dict[str, List[asyncio.Queue]] = defaultdict(list)

# Events endpoint for real-time streaming
@api_router.post("/events/emit")
async def emit_event(request: Request):
    """
    Handle real-time event emission from Temporal activities
    Stores events and forwards them to active SSE connections
    """
    try:
        event_data = await request.json()
        
        # Extract session info
        session_id = event_data.get("session_id", "unknown")
        event_type = event_data.get("event", "unknown")
        content_preview = event_data.get("content", "")[:50] + "..." if len(event_data.get("content", "")) > 50 else event_data.get("content", "")
        
        logger.info(f"Event received: {event_type} for session {session_id[:8]}... content: {content_preview}")
        
        # Store event for this session
        session_events[session_id].append(event_data)
        
        # Forward to all active streams for this session
        if session_id in active_streams:
            for queue in active_streams[session_id]:
                try:
                    queue.put_nowait(event_data)
                except asyncio.QueueFull:
                    logger.warning(f"Queue full for session {session_id[:8]}")
        
        return {"status": "event_received", "event": event_type}
        
    except Exception as e:
        logger.error(f"Error handling event emission: {e}")
        return {"status": "error", "message": str(e)}, 500

@api_router.get("/events/stream/{session_id}")
async def stream_events(session_id: str):
    """
    Server-Sent Events (SSE) endpoint for real-time streaming
    Frontend connects to this to receive events in real-time
    """
    async def event_generator():
        # Create a queue for this stream
        queue = asyncio.Queue(maxsize=50)
        
        # Register this stream for the session
        active_streams[session_id].append(queue)
        
        try:
            logger.info(f"SSE stream started for session {session_id[:8]}")
            
            # Send any recent events first
            recent_events = list(session_events[session_id])
            for event in recent_events[-5:]:  # Last 5 events
                yield f"data: {json.dumps(event)}\n\n"
            
            # Stream new events as they arrive
            while True:
                try:
                    # Wait for new event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    # If this is a completion event, close the stream
                    if event.get("event") == "RunCompleted":
                        logger.info(f"SSE stream completed for session {session_id[:8]}")
                        break
                        
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'event': 'keepalive', 'timestamp': int(time.time())})}\n\n"
                    
        except Exception as e:
            logger.error(f"Error in SSE stream for session {session_id[:8]}: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
        finally:
            # Clean up
            if queue in active_streams[session_id]:
                active_streams[session_id].remove(queue)
            if not active_streams[session_id]:
                del active_streams[session_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

# Models management endpoints
@api_router.post("/models/refresh")
async def refresh_models():
    """Fetch models from OpenRouter API and update database"""
    try:
        # Get OpenRouter API key from environment
        api_key = os.getenv("OPENROUTER_KEY")
        if not api_key:
            return {"error": "OpenRouter API key not found"}, 400
        
        async with httpx.AsyncClient() as client:
            # Fetch all free models
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                return {"error": "Failed to fetch models from OpenRouter"}, 500
            
            data = response.json()
            models_data = []
            
            for model in data.get("data", []):
                # Check if model is free (both prompt and completion pricing are "0")
                pricing = model.get("pricing", {})
                if pricing.get("prompt") == "0" and pricing.get("completion") == "0":
                    # Check if model supports tools
                    supported_params = model.get("supported_parameters", [])
                    is_tool_call = "tools" in supported_params if supported_params else False
                    
                    models_data.append({
                        "id": model["id"],
                        "name": model["name"],
                        "is_tool_call": is_tool_call,
                        "context_length": model.get("context_length", 0)
                    })
            
            # Save to database
            await db_manager.save_models(models_data)
            
            return {
                "status": "success",
                "message": f"Refreshed {len(models_data)} free models",
                "models_count": len(models_data),
                "tool_models_count": len([m for m in models_data if m["is_tool_call"]])
            }
            
    except Exception as e:
        logger.error(f"Error refreshing models: {e}")
        return {"error": str(e)}, 500

@api_router.get("/models")
async def get_models(tools_only: bool = False):
    """Get models from database, optionally filtered by tool call capability"""
    try:
        models = await db_manager.get_models(tools_only=tools_only)
        return {
            "status": "success", 
            "models": models,
            "count": len(models)
        }
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return {"error": str(e)}, 500

# Health check endpoint for the API
@api_router.get("/health")
async def api_health():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "api_version": "1.0.0",
        "available_endpoints": [
            "/sessions - Session management",
            "/chat - Chat completions and streaming", 
            "/events/emit - Real-time event emission",
            "/events/stream/{session_id} - SSE event streaming",
            "/models - Get models from database",
            "/models/refresh - Refresh models from OpenRouter",
            "/health - API health check"
        ],
        "active_streams": len(active_streams),
        "total_sessions_with_events": len(session_events)
    } 