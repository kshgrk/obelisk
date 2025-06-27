"""
OpenRouter Activities for Temporal Workflows
These activities handle all OpenRouter API interactions within Temporal workflows.
"""
import asyncio
import json
import time
import logging
from typing import Dict, Any, List, AsyncGenerator, Optional

import httpx
from temporalio import activity

from src.config.settings import settings

logger = logging.getLogger(__name__)


class OpenRouterError(Exception):
    """Custom exception for OpenRouter API errors"""
    pass


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
                    raise OpenRouterError("No choices in OpenRouter response")
                
                content = result["choices"][0]["message"]["content"]
                
                response_time = time.time() - start_time
                
                activity.logger.info(f"OpenRouter API call completed in {response_time:.2f}s")
                
                return {
                    "content": content,
                    "model": result.get("model", settings.openrouter.model),
                    "usage": result.get("usage", {}),
                    "response_time": response_time,
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
        Streaming chat completion with OpenRouter API
        """
        start_time = time.time()
        
        try:
            headers = {
                "Authorization": f"Bearer {settings.openrouter.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
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
            
            full_content = ""
            usage_info = {}
            model_used = settings.openrouter.model
            
            async with httpx.AsyncClient(timeout=settings.openrouter.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{settings.openrouter.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status_code != 200:
                        error_msg = f"OpenRouter streaming API error: {response.status_code} - {await response.aread()}"
                        activity.logger.error(error_msg)
                        raise OpenRouterError(error_msg)
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix
                            
                            if data.strip() == "[DONE]":
                                break
                            
                            try:
                                chunk = json.loads(data)
                                
                                if "choices" in chunk and chunk["choices"]:
                                    delta = chunk["choices"][0].get("delta", {})
                                    
                                    if "content" in delta and delta["content"]:
                                        full_content += delta["content"]
                                
                                # Store usage and model info if present
                                if "usage" in chunk:
                                    usage_info = chunk["usage"]
                                if "model" in chunk:
                                    model_used = chunk["model"]
                                    
                            except json.JSONDecodeError:
                                # Skip malformed JSON chunks
                                continue
            
            response_time = time.time() - start_time
            
            activity.logger.info(f"OpenRouter streaming API call completed in {response_time:.2f}s")
            
            return {
                "content": full_content,
                "model": model_used,
                "usage": usage_info,
                "response_time": response_time,
                "streaming": True
            }
            
        except httpx.TimeoutException:
            error_msg = f"OpenRouter streaming API timeout after {settings.openrouter.timeout}s"
            activity.logger.error(error_msg)
            raise OpenRouterError(error_msg)
        except httpx.RequestError as e:
            error_msg = f"OpenRouter streaming API request error: {e}"
            activity.logger.error(error_msg)
            raise OpenRouterError(error_msg)
        except Exception as e:
            activity.logger.error(f"Unexpected error in OpenRouter streaming API call: {e}")
            raise
    
    @staticmethod
    @activity.defn
    async def health_check() -> Dict[str, Any]:
        """
        Check OpenRouter API health and model availability
        """
        try:
            headers = {
                "Authorization": f"Bearer {settings.openrouter.api_key}",
                "Content-Type": "application/json"
            }
            
            # Simple test request to check API availability
            test_payload = {
                "model": settings.openrouter.model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5,
                "temperature": 0.1
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{settings.openrouter.base_url}/chat/completions",
                    headers=headers,
                    json=test_payload
                )
                
                is_healthy = response.status_code == 200
                
                return {
                    "healthy": is_healthy,
                    "status_code": response.status_code,
                    "model": settings.openrouter.model,
                    "base_url": settings.openrouter.base_url
                }
                
        except Exception as e:
            activity.logger.error(f"OpenRouter health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "model": settings.openrouter.model,
                "base_url": settings.openrouter.base_url
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
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{settings.openrouter.base_url}/models",
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_msg = f"Failed to get models: {response.status_code} - {response.text}"
                    activity.logger.error(error_msg)
                    raise OpenRouterError(error_msg)
                
                result = response.json()
                models = result.get("data", [])
                
                activity.logger.info(f"Retrieved {len(models)} models from OpenRouter")
                return models
                
        except Exception as e:
            activity.logger.error(f"Failed to get OpenRouter models: {e}")
            raise 