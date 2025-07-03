"""
OpenRouter Activities for Temporal workflows

This module provides OpenRouter API integration activities for use in Temporal workflows.
It handles both streaming and non-streaming chat completions with proper error handling.
Enhanced for tool calling support.
"""

import time
import json
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator
from uuid import uuid4
from datetime import datetime
from temporalio import activity
from src.config.settings import settings


class OpenRouterError(Exception):
    """Custom exception for OpenRouter API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ToolCallError(Exception):
    """Custom exception for tool calling errors"""
    def __init__(self, message: str, tool_name: Optional[str] = None):
        self.message = message
        self.tool_name = tool_name
        super().__init__(self.message)


class OpenRouterActivities:
    """OpenRouter activity implementations for Temporal workflows"""
    
    @staticmethod
    @activity.defn
    async def chat_completion(request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Non-streaming chat completion with OpenRouter API
        Enhanced with tool calling support
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
            
            # Use model from request, fallback to settings
            model = request_data.get("model", settings.openrouter.model)
            
            payload = {
                "model": model,
                "messages": request_data["messages"],
                "temperature": request_data.get("temperature", settings.openrouter.temperature),
                "max_tokens": request_data.get("max_tokens", settings.openrouter.max_tokens),
                "stream": False
            }
            
            # Add tool definitions if provided
            if "tools" in request_data and request_data["tools"]:
                payload["tools"] = request_data["tools"]
                # Force tool calling if tools are available
                if "tool_choice" in request_data:
                    payload["tool_choice"] = request_data["tool_choice"]
                else:
                    payload["tool_choice"] = "auto"  # Let model decide when to use tools
                
                activity.logger.info(f"Making OpenRouter API call with {len(request_data['tools'])} tools for model: {payload['model']}")
            else:
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
                    raise OpenRouterError(error_msg, response.status_code)
                
                result = response.json()
                
                # Extract the response content
                if "choices" not in result or not result["choices"]:
                    error_msg = "No choices in OpenRouter response"
                    raise OpenRouterError(error_msg)
                
                choice = result["choices"][0]
                message = choice["message"]
                response_time = time.time() - start_time
                
                # Handle tool calls if present
                tool_calls = message.get("tool_calls", [])
                has_tool_calls = bool(tool_calls)
                
                activity.logger.info(f"OpenRouter API call completed in {response_time:.2f}s, tool calls: {len(tool_calls)}")
                
                response_data = {
                    "content": message.get("content", ""),
                    "model": result.get("model", model),
                    "usage": result.get("usage", {}),
                    "response_time_ms": response_time * 1000,
                    "finish_reason": choice.get("finish_reason", "stop"),
                    "streaming": False,
                    "has_tool_calls": has_tool_calls,
                    "tool_calls": tool_calls,
                    "message": message  # Include full message for tool calling
                }
                
                return response_data
                
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
    async def chat_completion_with_tools(
        request_data: Dict[str, Any], 
        tool_schemas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Chat completion with explicit tool definitions
        """
        # Add tools to request data
        enhanced_request = request_data.copy()
        enhanced_request["tools"] = tool_schemas
        
        return await OpenRouterActivities.chat_completion(enhanced_request)
    
    @staticmethod
    @activity.defn
    async def stream_chat(request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Streaming chat completion with real-time event emission
        Enhanced with tool calling support
        """
        start_time = time.time()
        session_id = request_data.get("session_id", "unknown")
        
        try:
            # Import event emission functionality
            import requests
            import uuid
            
            # Prepare request for streaming
            headers = {
                "Authorization": f"Bearer {settings.openrouter.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/your-app/obelisk",
                "X-Title": "Obelisk Chat Server"
            }
            
            # Use model from request, fallback to settings
            model = request_data.get("model", settings.openrouter.model)
            
            payload = {
                "model": model,
                "messages": request_data["messages"],
                "temperature": request_data.get("temperature", settings.openrouter.temperature),
                "max_tokens": request_data.get("max_tokens", settings.openrouter.max_tokens),
                "stream": True
            }
            
            # Add tool definitions if provided
            has_tools = False
            if "tools" in request_data and request_data["tools"]:
                payload["tools"] = request_data["tools"]
                if "tool_choice" in request_data:
                    payload["tool_choice"] = request_data["tool_choice"]
                else:
                    payload["tool_choice"] = "auto"
                has_tools = True
                
                activity.logger.info(f"Making streaming OpenRouter API call with {len(request_data['tools'])} tools for model: {payload['model']}")
            else:
                activity.logger.info(f"Making streaming OpenRouter API call for model: {payload['model']}")
            
            # Generate run ID for this streaming session
            run_id = f"run-{uuid.uuid4()}"
            full_content = ""
            chunk_count = 0
            tool_calls_buffer = []  # Buffer for accumulating tool calls
            current_tool_call = None
            
            # Emit start event
            start_event = {
                "event": "RunStarted",
                "content": "Run started",
                "content_type": "str",
                "member_responses": [],
                "run_id": run_id,
                "session_id": session_id,
                "has_tools": has_tools,
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
                        raise OpenRouterError(error_msg, response.status_code)
                    
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
                                    
                                    # Handle content streaming
                                    content = delta.get("content", "")
                                    if content:
                                        full_content += content
                                        chunk_count += 1
                                        
                                        # Emit real-time chunk event
                                        chunk_event = {
                                            "event": "RunResponse",
                                            "content": content,
                                            "content_type": "str",
                                            "member_responses": [],
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
                                    
                                    # Handle tool calls streaming
                                    if "tool_calls" in delta:
                                        tool_calls = delta["tool_calls"]
                                        for tool_call_delta in tool_calls:
                                            call_index = tool_call_delta.get("index", 0)
                                            
                                            # Ensure we have enough space in buffer
                                            while len(tool_calls_buffer) <= call_index:
                                                tool_calls_buffer.append({
                                                    "id": "",
                                                    "type": "function",
                                                    "function": {"name": "", "arguments": ""}
                                                })
                                            
                                            # Update tool call data
                                            if "id" in tool_call_delta:
                                                tool_calls_buffer[call_index]["id"] = tool_call_delta["id"]
                                            
                                            if "function" in tool_call_delta:
                                                func_delta = tool_call_delta["function"]
                                                if "name" in func_delta and func_delta["name"] is not None:
                                                    # Ensure the current name is a string before concatenation
                                                    current_name = tool_calls_buffer[call_index]["function"]["name"]
                                                    if current_name is None:
                                                        current_name = ""
                                                    tool_calls_buffer[call_index]["function"]["name"] = current_name + func_delta["name"]
                                                if "arguments" in func_delta and func_delta["arguments"] is not None:
                                                    # Ensure the current arguments is a string before concatenation
                                                    current_args = tool_calls_buffer[call_index]["function"]["arguments"]
                                                    if current_args is None:
                                                        current_args = ""
                                                    tool_calls_buffer[call_index]["function"]["arguments"] = current_args + func_delta["arguments"]
                                        
                                        # Emit tool call event
                                        try:
                                            tool_event = {
                                                "event": "ToolCallsStreaming",
                                                "content": "Tool calls being constructed",
                                                "content_type": "tool_calls",
                                                "tool_calls": tool_calls_buffer,
                                                "run_id": run_id,
                                                "session_id": session_id,
                                                "created_at": int(time.time())
                                            }
                                            requests.post(
                                                "http://localhost:8001/events/emit",
                                                json=tool_event,
                                                timeout=0.5
                                            )
                                        except:
                                            pass
                                        
                            except json.JSONDecodeError:
                                activity.logger.warning(f"Failed to parse streaming chunk: {data}")
                                continue
            
            response_time = time.time() - start_time
            
            # Process completed tool calls
            processed_tool_calls = []
            for i, tool_call in enumerate(tool_calls_buffer):
                # A valid tool call must have a function name and non-empty arguments
                # ID can be null in some streaming scenarios, so we don't require it
                if (tool_call["function"]["name"] and 
                    tool_call["function"]["arguments"] and 
                    tool_call["function"]["arguments"].strip()):
                    try:
                        # Generate ID if missing
                        if not tool_call["id"]:
                            tool_call["id"] = f"call_{str(uuid4())[:12]}"
                        
                        # Parse arguments JSON
                        args_str = tool_call["function"]["arguments"]
                        if args_str:
                            tool_call["function"]["arguments"] = json.loads(args_str)
                        else:
                            tool_call["function"]["arguments"] = {}
                        processed_tool_calls.append(tool_call)
                        activity.logger.info(f"Processed tool call {i}: {tool_call['function']['name']} with args {tool_call['function']['arguments']}")
                    except json.JSONDecodeError:
                        activity.logger.warning(f"Failed to parse tool call arguments: {args_str}")
                        tool_call["function"]["arguments"] = {}
                        processed_tool_calls.append(tool_call)
                else:
                    activity.logger.debug(f"Skipping incomplete tool call {i}: name='{tool_call['function']['name']}', args='{tool_call['function']['arguments']}'")
            
            # Emit completion event with full metadata
            completion_event = {
                "event": "RunCompleted",
                "content": full_content,
                "content_type": "str",
                "model": model,
                "member_responses": [],
                "run_id": run_id,
                "session_id": session_id,
                "has_tool_calls": len(processed_tool_calls) > 0,
                "tool_calls": processed_tool_calls,
                "created_at": int(time.time()),
                "messages": [
                    {
                        "role": "user",
                        "content": request_data["messages"][-1]["content"] if request_data["messages"] else "",
                        "from_history": False,
                        "stop_after_tool_call": False,
                        "created_at": int(start_time)
                    },
                    {
                        "role": "assistant",
                        "content": full_content,
                        "tool_calls": processed_tool_calls if processed_tool_calls else None,
                        "from_history": False,
                        "stop_after_tool_call": False,
                        "metrics": {
                            "input_tokens": 0,  # Will be populated by actual API response if available
                            "output_tokens": 0,  # Will be populated by actual API response if available
                            "total_tokens": 0,   # Will be populated by actual API response if available
                            "time": response_time,
                            "time_to_first_token": 0  # Could be calculated if needed
                        },
                        "model": model,
                        "created_at": int(start_time)
                    }
                ]
            }
            
            try:
                requests.post(
                    "http://localhost:8001/events/emit",
                    json=completion_event,
                    timeout=1.0
                )
            except:
                pass  # Event emission is optional
            
            activity.logger.info(f"OpenRouter streaming API call completed in {response_time:.2f}s, tool calls: {len(processed_tool_calls)}")
            
            return {
                "content": full_content,
                "model": model,
                "response_time_ms": response_time * 1000,
                "chunk_count": chunk_count,
                "streaming": True,
                "finish_reason": "tool_calls" if processed_tool_calls else "stop",
                "run_id": run_id,
                "has_tool_calls": len(processed_tool_calls) > 0,
                "tool_calls": processed_tool_calls
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
    async def extract_tool_call_parameters(tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract and validate tool call parameters from OpenRouter response
        
        Args:
            tool_calls: List of tool calls from OpenRouter response
            
        Returns:
            Dict with extracted and validated parameters
        """
        start_time = time.time()
        
        try:
            activity.logger.info(f"Extracting parameters from {len(tool_calls)} tool calls")
            
            extracted_calls = []
            validation_errors = []
            
            for i, tool_call in enumerate(tool_calls):
                try:
                    # Extract basic tool call information
                    call_data = {
                        "id": tool_call.get("id", f"call_{str(uuid4())[:8]}"),
                        "type": tool_call.get("type", "function"),
                        "tool_name": "",
                        "parameters": {},
                        "raw_tool_call": tool_call
                    }
                    
                    # Extract function information
                    if "function" in tool_call:
                        function_data = tool_call["function"]
                        call_data["tool_name"] = function_data.get("name", "")
                        
                        # Parse arguments
                        arguments = function_data.get("arguments", {})
                        if isinstance(arguments, str):
                            try:
                                call_data["parameters"] = json.loads(arguments)
                            except json.JSONDecodeError as e:
                                validation_errors.append({
                                    "call_index": i,
                                    "tool_name": call_data["tool_name"],
                                    "error": f"Failed to parse arguments JSON: {str(e)}",
                                    "raw_arguments": arguments
                                })
                                call_data["parameters"] = {}
                        elif isinstance(arguments, dict):
                            call_data["parameters"] = arguments
                        else:
                            validation_errors.append({
                                "call_index": i,
                                "tool_name": call_data["tool_name"],
                                "error": f"Invalid arguments type: {type(arguments)}",
                                "raw_arguments": arguments
                            })
                            call_data["parameters"] = {}
                    
                    # Validate required fields
                    if not call_data["tool_name"]:
                        validation_errors.append({
                            "call_index": i,
                            "error": "Missing tool name",
                            "raw_tool_call": tool_call
                        })
                    
                    extracted_calls.append(call_data)
                    
                except Exception as e:
                    validation_errors.append({
                        "call_index": i,
                        "error": f"Failed to process tool call: {str(e)}",
                        "raw_tool_call": tool_call
                    })
            
            extraction_time = time.time() - start_time
            
            result = {
                "success": True,
                "extracted_calls": extracted_calls,
                "total_calls": len(tool_calls),
                "valid_calls": len([call for call in extracted_calls if call["tool_name"]]),
                "validation_errors": validation_errors,
                "has_errors": len(validation_errors) > 0,
                "extraction_time_ms": extraction_time * 1000,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            activity.logger.info(f"Tool call parameter extraction completed: {result['valid_calls']}/{result['total_calls']} valid calls")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to extract tool call parameters: {e}")
            return {
                "success": False,
                "extracted_calls": [],
                "total_calls": len(tool_calls),
                "valid_calls": 0,
                "validation_errors": [{"error": f"Extraction failed: {str(e)}"}],
                "has_errors": True,
                "extraction_time_ms": (time.time() - start_time) * 1000,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    @activity.defn
    async def inject_tool_results_into_conversation(
        messages: List[Dict[str, Any]], 
        tool_results: List[Dict[str, Any]],
        assistant_message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Inject tool call results back into conversation for continuation
        
        Args:
            messages: Original conversation messages
            tool_results: Results from tool executions
            assistant_message: The assistant message with tool calls
            
        Returns:
            Dict with updated conversation for continuation
        """
        start_time = time.time()
        
        try:
            activity.logger.info(f"Injecting {len(tool_results)} tool results into conversation")
            
            # Create new conversation with tool results
            updated_messages = messages.copy()
            
            # Add the assistant message with tool calls
            assistant_msg = {
                "role": "assistant",
                "content": assistant_message.get("content", ""),
            }
            
            # Add tool calls if present
            if assistant_message.get("tool_calls"):
                assistant_msg["tool_calls"] = assistant_message["tool_calls"]
            
            updated_messages.append(assistant_msg)
            
            # Add tool result messages
            for result in tool_results:
                tool_message = {
                    "role": "tool",
                    "tool_call_id": result.get("call_id", result.get("tool_call_id")),
                    "name": result.get("tool_name", "unknown"),
                    "content": json.dumps(result.get("result", {})) if result.get("result") else ""
                }
                
                # Add error information if tool call failed
                if not result.get("success", True) and result.get("error"):
                    tool_message["content"] = json.dumps({
                        "error": result["error"],
                        "success": False
                    })
                
                updated_messages.append(tool_message)
            
            injection_time = time.time() - start_time
            
            result = {
                "success": True,
                "updated_messages": updated_messages,
                "original_message_count": len(messages),
                "updated_message_count": len(updated_messages),
                "tool_results_injected": len(tool_results),
                "injection_time_ms": injection_time * 1000,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            activity.logger.info(f"Tool results injection completed: {len(tool_results)} results injected")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to inject tool results into conversation: {e}")
            return {
                "success": False,
                "updated_messages": messages,
                "original_message_count": len(messages),
                "updated_message_count": len(messages),
                "tool_results_injected": 0,
                "error": str(e),
                "injection_time_ms": (time.time() - start_time) * 1000,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    @activity.defn
    async def continue_conversation_after_tools(
        messages_with_tool_results: List[Dict[str, Any]],
        model: str,
        request_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Continue conversation after tool execution with updated context
        
        Args:
            messages_with_tool_results: Messages including tool results
            model: Model to use for continuation
            request_options: Additional request options
            
        Returns:
            Dict with continued conversation response
        """
        start_time = time.time()
        
        try:
            activity.logger.info(f"Continuing conversation after tool execution with {len(messages_with_tool_results)} messages")
            
            # Prepare continuation request
            continuation_request = {
                "model": model,
                "messages": messages_with_tool_results,
                **(request_options or {})
            }
            
            # Remove tools from continuation to prevent infinite tool calling
            if "tools" in continuation_request:
                del continuation_request["tools"]
            if "tool_choice" in continuation_request:
                del continuation_request["tool_choice"]
            
            # Make the continuation call
            response = await OpenRouterActivities.chat_completion(continuation_request)
            
            continuation_time = time.time() - start_time
            
            # Add metadata about continuation
            response.update({
                "is_continuation": True,
                "continuation_after_tools": True,
                "continuation_time_ms": continuation_time * 1000,
                "message_count_with_tools": len(messages_with_tool_results)
            })
            
            activity.logger.info(f"Conversation continuation completed in {continuation_time:.2f}s")
            return response
            
        except Exception as e:
            activity.logger.error(f"Failed to continue conversation after tools: {e}")
            return {
                "success": False,
                "error": str(e),
                "is_continuation": True,
                "continuation_after_tools": True,
                "continuation_time_ms": (time.time() - start_time) * 1000,
                "timestamp": datetime.utcnow().isoformat()
            }

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