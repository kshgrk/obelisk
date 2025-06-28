"""
Chat API routes using Temporal workflows
"""

import uuid
import json
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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

async def get_temporal_client():
    """Get connected Temporal client"""
    try:
        client = await temporal_client.connect()
        return client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Temporal: {str(e)}")

async def execute_temporal_workflow(session_id: str, message: str, streaming: bool = True) -> str:
    """Execute Temporal workflow for chat"""
    client = await get_temporal_client()
    
    try:
        # Generate unique workflow ID
        workflow_id = f"chat-{session_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        
        if streaming:
            # Use streaming workflow
            workflow_handle = await client.start_workflow(
                SimpleStreamingChatWorkflow.run,
                args=[session_id, message],
                id=workflow_id,
                task_queue=settings.temporal.task_queue,
            )
        else:
            # Use regular workflow
            workflow_handle = await client.start_workflow(
                SimpleChatWorkflow.run,
                args=[session_id, message, streaming],
                id=workflow_id,
                task_queue=settings.temporal.task_queue,
            )
        
        # Wait for workflow completion
        result = await workflow_handle.result()
        
        return result.get("content", "No response received")
        
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
        
        # Generate a session ID from the request (could be improved with actual session management)
        session_id = f"completion-{uuid.uuid4().hex[:8]}"
        
        # Execute via Temporal workflow
        response_content = await execute_temporal_workflow(
            session_id=session_id,
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
    Simple chat endpoint using Temporal workflows
    """
    try:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Execute via Temporal workflow
        response_content = await execute_temporal_workflow(
            session_id=request.session_id,
            message=request.message,
            streaming=request.stream or True
        )
        
        if request.stream:
            # For streaming, return content in chunks
            def generate_stream():
                words = response_content.split()
                for i, word in enumerate(words):
                    chunk = {
                        "content": word + (" " if i < len(words) - 1 else ""),
                        "done": i == len(words) - 1
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(generate_stream(), media_type="text/plain")
        
        # Non-streaming response
        return {
            "session_id": request.session_id,
            "message": request.message,
            "response": response_content,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 