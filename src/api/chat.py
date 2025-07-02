"""
Chat API routes using Temporal workflows
"""

import uuid
import json
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import logging
import asyncio

logger = logging.getLogger(__name__)

from src.config.settings import settings
from src.temporal.client import temporal_client
from src.temporal.workflows.simple_chat import SimpleChatWorkflow, SimpleStreamingChatWorkflow

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: list[ChatMessage]
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

class SimpleChatRequest(BaseModel):
    session_id: str
    message: str
    stream: Optional[bool] = True
    config_override: Optional[dict] = None

async def get_temporal_client():
    """Get connected Temporal client"""
    try:
        client = await temporal_client.connect()
        return client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Temporal: {str(e)}")

async def execute_temporal_workflow(session_id: str, message: str, config_override: Optional[dict] = None, streaming: bool = True) -> str:
    """Execute Temporal workflow for chat"""
    client = await get_temporal_client()
    
    try:
        # Generate unique workflow ID
        workflow_id = f"chat-{session_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        
        # Always use SimpleChatWorkflow with streaming parameter
        workflow_handle = await client.start_workflow(
            SimpleChatWorkflow.run,
            args=[session_id, message, config_override, streaming],
            id=workflow_id,
            task_queue=settings.temporal.task_queue,
        )
        
        # Wait for workflow completion
        result = await workflow_handle.result()
        
        # Handle workflow result properly
        if isinstance(result, dict):
            if result.get("success", False):
                return result.get("content", "No response received")
            else:
                # Handle error case
                error_msg = result.get("error", "Unknown workflow error")
                raise HTTPException(status_code=500, detail=f"Workflow failed: {error_msg}")
        else:
            # If result is not a dict, try to use it as string
            return str(result) if result else "No response received"
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Temporal workflow error: {str(e)}")
    finally:
        await temporal_client.disconnect()

@router.post("/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenRouter-compatible chat completions endpoint using Temporal workflows
    """
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="Messages cannot be empty")
        
        # Use the last message as the user input
        last_message = request.messages[-1]
        if last_message.role != "user":
            raise HTTPException(status_code=400, detail="Last message must be from user")
        
        # Create a temporary session for this completion request
        from src.database.manager import db_manager
        from src.models.chat import ChatSessionCreate
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Generate a session ID and create the session
        temp_session_name = f"completion-{uuid.uuid4().hex[:8]}"
        session_data = ChatSessionCreate(name=temp_session_name)
        
        # Ensure database is initialized
        await db_manager.initialize()
        
        # Create the session
        session = await db_manager.create_session(session_data)
        session_id = session.id  # This is the UUID, not the name
        
        # Debug logging to ensure we're using the right ID
        logger.info(f"Created completion session: name='{temp_session_name}', id='{session_id}'")
        logger.info(f"About to execute workflow with session_id='{session_id}' (type: {type(session_id)})")
        
        # Execute via Temporal workflow
        response_content = await execute_temporal_workflow(
            session_id=session_id,  # Make sure this is the UUID, not the name
            message=last_message.content,
            streaming=request.stream or False
        )
        
        if request.stream:
            # For streaming, we'll return the content immediately for now
            # In a real implementation, you'd want to stream from the workflow
            def generate_stream():
                lines = response_content.split('\n')
                for i, line in enumerate(lines):
                    chunk = {
                        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                        "object": "chat.completion.chunk",
                        "created": int(datetime.now().timestamp()),
                        "model": request.model or settings.openrouter.model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": line + ('\n' if i < len(lines) - 1 else '')},
                            "finish_reason": "stop" if i == len(lines) - 1 else None
                        }]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(generate_stream(), media_type="text/plain")
        
        # Non-streaming response
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": request.model or settings.openrouter.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(last_message.content.split()),
                "completion_tokens": len(response_content.split()),
                "total_tokens": len(last_message.content.split()) + len(response_content.split())
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def simple_chat(request: SimpleChatRequest):
    """
    Simple chat endpoint using Temporal workflows with real-time streaming
    """
    try:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        if request.stream:
            # For streaming: start workflow asynchronously and stream via SSE
            return await start_streaming_workflow(request.session_id, request.message, request.config_override)
        else:
            # For non-streaming: wait for workflow completion
            response_content = await execute_temporal_workflow(
                session_id=request.session_id,
                message=request.message,
                config_override=request.config_override,
                streaming=False
            )
            
            return {
                "session_id": request.session_id,
                "message": request.message,
                "response": response_content,
                "streaming": False,
                "timestamp": datetime.now().isoformat()
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def start_streaming_workflow(session_id: str, message: str, config_override: Optional[dict] = None):
    """
    Start Temporal workflow asynchronously and return real-time SSE stream
    """
    try:
        # Import the event system from router
        from .router import active_streams, session_events
        
        # Start the workflow asynchronously (don't wait for completion)
        client = await get_temporal_client()
        
        # Generate unique workflow ID
        workflow_id = f"chat-{session_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        
        # Start the streaming workflow asynchronously
        workflow_handle = await client.start_workflow(
            SimpleStreamingChatWorkflow.run,
            args=[session_id, message, config_override, True],
            id=workflow_id,
            task_queue=settings.temporal.task_queue,
        )
        
        # Disconnect from Temporal client (workflow continues running)
        await temporal_client.disconnect()
        
        # Immediately return SSE stream that will receive events
        async def event_stream():
            import time
            
            # Create a queue for this stream
            queue = asyncio.Queue(maxsize=50)
            
            # Register this stream for the session
            active_streams[session_id].append(queue)
            
            try:
                logger.info(f"Direct SSE stream started for session {session_id[:8]}")
                
                # Clear old events to prevent mixing with new request
                session_events[session_id].clear()
                
                # Stream new events as they arrive (don't send old events)
                while True:
                    try:
                        # Wait for new event with timeout
                        event = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"data: {json.dumps(event)}\n\n"
                        
                        # If this is a completion event, close the stream
                        if event.get("event") == "RunCompleted":
                            logger.info(f"Direct SSE stream completed for session {session_id[:8]}")
                            break
                            
                    except asyncio.TimeoutError:
                        # Send keepalive
                        yield f"data: {json.dumps({'event': 'keepalive', 'timestamp': int(time.time())})}\n\n"
                        
            except Exception as e:
                logger.error(f"Error in direct SSE stream for session {session_id[:8]}: {e}")
                yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
            finally:
                # Clean up
                if queue in active_streams[session_id]:
                    active_streams[session_id].remove(queue)
                if not active_streams[session_id]:
                    del active_streams[session_id]
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive", 
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start streaming workflow: {str(e)}") 