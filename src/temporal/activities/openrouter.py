"""
OpenRouter Activities for Temporal workflows

This module provides OpenRouter API integration activities for use in Temporal workflows.
It handles both streaming and non-streaming chat completions with proper error handling.
"""

import time
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator
from temporalio import activity
from src.config.settings import settings


class OpenRouterError(Exception):
    """Custom exception for OpenRouter API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class OpenRouterActivities:
    """OpenRouter activity implementations for Temporal workflows"""
    
    @staticmethod
    @activity.defn
    async def chat_completion(request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Non-streaming chat completion with OpenRouter API
        """
        start_time = time.time()
        
        try:
            # Prepare request
            headers = {
                "Authorization": f"Bearer {settings.openrouter.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/your-app/obelisk",  # Optional
                "X-Title": "Obelisk Chat Server"  # Optional
            }
            
            payload = {
                "model": settings.openrouter.model,
                "messages": request_data["messages"],
                "temperature": request_data.get("temperature", settings.openrouter.temperature),
                "max_tokens": request_data.get("max_tokens", settings.openrouter.max_tokens),
                "stream": False
            }
            
            activity.logger.info(f"Making OpenRouter API call for model: {payload['model']}")
            
            async with httpx.AsyncClient(timeout=settings.openrouter.timeout) as client:
                response = await client.post(
                    f"{settings.openrouter.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    error_msg = f"OpenRouter API error: {response.status_code} - {response.text}"
                    activity.logger.error(error_msg)
                    raise OpenRouterError(error_msg)
                
                result = response.json()
                
                # Extract the response content
                if "choices" not in result or not result["choices"]:
                    error_msg = "No choices in OpenRouter response"
                    raise OpenRouterError(error_msg)
                
                content = result["choices"][0]["message"]["content"]
                response_time = time.time() - start_time
                
                activity.logger.info(f"OpenRouter API call completed in {response_time:.2f}s")
                
                return {
                    "content": content,
                    "model": result.get("model", settings.openrouter.model),
                    "usage": result.get("usage", {}),
                    "response_time_ms": response_time * 1000,
                    "finish_reason": result["choices"][0].get("finish_reason", "stop"),
                    "streaming": False
                }
                
        except httpx.TimeoutException:
            error_msg = f"OpenRouter API timeout after {settings.openrouter.timeout}s"
            activity.logger.error(error_msg)
            raise OpenRouterError(error_msg)
        except httpx.RequestError as e:
            error_msg = f"OpenRouter API request error: {e}"
            activity.logger.error(error_msg)
            raise OpenRouterError(error_msg)
        except Exception as e:
            activity.logger.error(f"Unexpected error in OpenRouter API call: {e}")
            raise
    
    @staticmethod
    @activity.defn
    async def stream_chat(request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Streaming chat completion with real-time event emission
        """
        start_time = time.time()
        session_id = request_data.get("session_id", "unknown")
        
        try:
            # Import event emission functionality
            import json
            import httpx
            import requests
            from datetime import datetime
            import uuid
            
            # Prepare request for streaming
            headers = {
                "Authorization": f"Bearer {settings.openrouter.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/your-app/obelisk",
                "X-Title": "Obelisk Chat Server"
            }
            
            payload = {
                "model": settings.openrouter.model,
                "messages": request_data["messages"],
                "temperature": request_data.get("temperature", settings.openrouter.temperature),
                "max_tokens": request_data.get("max_tokens", settings.openrouter.max_tokens),
                "stream": True
            }
            
            activity.logger.info(f"Making streaming OpenRouter API call for model: {payload['model']}")
            
            # Generate run ID for this streaming session
            run_id = f"run-{uuid.uuid4()}"
            full_content = ""
            chunk_count = 0
            
            # Emit start event
            start_event = {
                "event": "RunStarted",
                "content": "Run started",
                "content_type": "str",
                "run_id": run_id,
                "session_id": session_id,
                "created_at": int(time.time())
            }
            
            # Try to emit event to local event server if available
            try:
                event_response = requests.post(
                    "http://localhost:8001/events/emit",
                    json=start_event,
                    timeout=1.0
                )
            except:
                pass  # Event emission is optional
            
            async with httpx.AsyncClient(timeout=settings.openrouter.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{settings.openrouter.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_msg = f"OpenRouter API error: {response.status_code} - {error_text.decode()}"
                        activity.logger.error(error_msg)
                        raise OpenRouterError(error_msg)
                    
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                            
                        if line.startswith("data: "):
                            data = line[6:].strip()
                            
                            if data == "[DONE]":
                                break
                                
                            try:
                                chunk_data = json.loads(data)
                                
                                if "choices" in chunk_data and chunk_data["choices"]:
                                    delta = chunk_data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    
                                    if content:
                                        full_content += content
                                        chunk_count += 1
                                        
                                        # Emit real-time chunk event
                                        chunk_event = {
                                            "event": "RunResponse",
                                            "content": content,
                                            "content_type": "str",
                                            "run_id": run_id,
                                            "session_id": session_id,
                                            "created_at": int(time.time())
                                        }
                                        
                                        # Try to emit event to local event server
                                        try:
                                            requests.post(
                                                "http://localhost:8001/events/emit",
                                                json=chunk_event,
                                                timeout=0.5
                                            )
                                        except:
                                            pass  # Event emission is optional
                                        
                            except json.JSONDecodeError:
                                activity.logger.warning(f"Failed to parse streaming chunk: {data}")
                                continue
            
            response_time = time.time() - start_time
            
            # Emit completion event
            completion_event = {
                "event": "RunCompleted",
                "content": full_content,
                "content_type": "str",
                "run_id": run_id,
                "session_id": session_id,
                "created_at": int(time.time()),
                "final_content": full_content,
                "refresh_conversation": True
            }
            
            try:
                requests.post(
                    "http://localhost:8001/events/emit",
                    json=completion_event,
                    timeout=1.0
                )
            except:
                pass  # Event emission is optional
            
            activity.logger.info(f"OpenRouter streaming API call completed in {response_time:.2f}s")
            
            return {
                "content": full_content,
                "model": settings.openrouter.model,
                "response_time_ms": response_time * 1000,
                "chunk_count": chunk_count,
                "streaming": True,
                "finish_reason": "stop",
                "run_id": run_id
            }
            
        except httpx.TimeoutException:
            error_msg = f"OpenRouter streaming timeout after {settings.openrouter.timeout}s"
            activity.logger.error(error_msg)
            raise OpenRouterError(error_msg)
        except httpx.RequestError as e:
            error_msg = f"OpenRouter streaming request error: {e}"
            activity.logger.error(error_msg)
            raise OpenRouterError(error_msg)
        except Exception as e:
            activity.logger.error(f"Unexpected error in OpenRouter streaming: {e}")
            raise

    @staticmethod
    @activity.defn
    async def health_check() -> Dict[str, Any]:
        """
        Health check for OpenRouter API connectivity
        """
        try:
            headers = {
                "Authorization": f"Bearer {settings.openrouter.api_key}",
                "Content-Type": "application/json",
            }
            
            # Simple request to check API availability
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.openrouter.base_url}/models",
                    headers=headers
                )
                
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "api_available": True,
                        "model": settings.openrouter.model,
                        "timestamp": time.time()
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "api_available": False,
                        "error": f"HTTP {response.status_code}",
                        "timestamp": time.time()
                    }
                    
        except Exception as e:
            return {
                "status": "unhealthy",
                "api_available": False,
                "error": str(e),
                "timestamp": time.time()
            }

    @staticmethod
    @activity.defn
    async def get_models() -> List[Dict[str, Any]]:
        """
        Get available models from OpenRouter API
        """
        try:
            headers = {
                "Authorization": f"Bearer {settings.openrouter.api_key}",
                "Content-Type": "application/json",
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{settings.openrouter.base_url}/models",
                    headers=headers
                )
                
                if response.status_code == 200:
                    models_data = response.json()
                    return models_data.get("data", [])
                else:
                    activity.logger.error(f"Failed to get models: {response.status_code}")
                    raise OpenRouterError(f"Failed to get models: {response.status_code}")
                    
        except httpx.RequestError as e:
            activity.logger.error(f"Request error getting models: {e}")
            raise OpenRouterError(f"Request error: {e}")
        except Exception as e:
            activity.logger.error(f"Unexpected error getting models: {e}")
            raise 