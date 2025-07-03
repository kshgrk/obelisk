"""
Tool Calling Activities for Temporal Workflows

This module provides tool calling integration activities for use in Temporal workflows.
It handles model capability checking, tool registration with OpenRouter, tool execution,
and result formatting for conversation history.
"""

import time
import json
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from temporalio import activity

from src.tools import tool_registry
from src.tools.schemas import ToolCall, ToolCallResult, ToolCallStatus, ToolExecutionContext
from src.tools.exceptions import ToolError, ToolNotFoundError, ToolPermissionError
from src.models.capabilities import ModelCapabilityManager
from src.config.settings import settings


class ToolCallingError(Exception):
    """Custom exception for tool calling errors"""
    def __init__(self, message: str, tool_name: Optional[str] = None, error_code: Optional[str] = None):
        self.message = message
        self.tool_name = tool_name
        self.error_code = error_code
        super().__init__(self.message)


class ToolCallingActivities:
    """Tool calling activity implementations for Temporal workflows"""
    
    @staticmethod
    @activity.defn
    async def check_model_tool_support(model_id: str) -> Dict[str, Any]:
        """
        Check if a specific model supports tool calling
        
        Args:
            model_id: ID of the model to check
            
        Returns:
            Dict with model capability information
        """
        start_time = time.time()
        
        try:
            activity.logger.info(f"Checking tool calling support for model: {model_id}")
            
            # Initialize capability manager if needed
            capability_manager = ModelCapabilityManager()
            await capability_manager.initialize()
            
            # Check if model supports tool calling
            supports_tools = await capability_manager.supports_tool_calls(model_id)
            model_capability = await capability_manager.get_model_capability(model_id)
            
            result = {
                "model_id": model_id,
                "supports_tool_calls": supports_tools,
                "capability_info": {
                    "name": model_capability.name if model_capability else "Unknown",
                    "context_length": model_capability.context_length if model_capability else 0,
                    "supports_tool_calls": model_capability.supports_tool_calls if model_capability else False
                } if model_capability else None,
                "check_time": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            activity.logger.info(f"Model {model_id} tool support check completed: {supports_tools}")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to check tool support for model {model_id}: {e}")
            return {
                "model_id": model_id,
                "supports_tool_calls": False,
                "error": str(e),
                "check_time": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    @activity.defn
    async def register_tools_with_openrouter(model_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Register available tools with OpenRouter API for the specified model
        
        Args:
            model_id: Model to register tools for
            session_id: Optional session ID for context
            
        Returns:
            Dict with registration results
        """
        start_time = time.time()
        
        try:
            activity.logger.info(f"Registering tools with OpenRouter for model: {model_id}")
            
            # Ensure tool registry is initialized
            if not tool_registry._initialized:
                tool_registry.initialize()
            
            # Check if model supports tools
            model_check = await ToolCallingActivities.check_model_tool_support(model_id)
            if not model_check.get("supports_tool_calls", False):
                return {
                    "model_id": model_id,
                    "registration_success": False,
                    "error": f"Model {model_id} does not support tool calling",
                    "tools_registered": [],
                    "registration_time": time.time() - start_time,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Get compatible tools for this model
            compatible_tools = await tool_registry.get_tools_for_model(model_id)
            
            if not compatible_tools:
                return {
                    "model_id": model_id,
                    "registration_success": True,
                    "message": "No compatible tools found for this model",
                    "tools_registered": [],
                    "registration_time": time.time() - start_time,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Generate OpenRouter-compatible tool schemas
            tool_schemas = []
            registered_tools = []
            
            for tool_name in compatible_tools:
                try:
                    # Check permissions if session provided
                    if session_id:
                        has_permission = tool_registry.check_tool_permission(
                            tool_name, session_id, "user", model_id
                        )
                        if not has_permission:
                            activity.logger.warning(f"Tool {tool_name} denied for session {session_id}")
                            continue
                    
                    # Get tool and generate schema
                    tool = tool_registry.get_tool(tool_name)
                    schema = tool.get_openrouter_schema()
                    tool_schemas.append(schema)
                    registered_tools.append(tool_name)
                    
                except Exception as e:
                    activity.logger.warning(f"Failed to register tool {tool_name}: {e}")
            
            result = {
                "model_id": model_id,
                "session_id": session_id,
                "registration_success": True,
                "tools_registered": registered_tools,
                "tool_schemas": tool_schemas,
                "total_tools": len(registered_tools),
                "registration_time": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            activity.logger.info(f"Successfully registered {len(registered_tools)} tools for model {model_id}")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to register tools with OpenRouter for model {model_id}: {e}")
            return {
                "model_id": model_id,
                "session_id": session_id,
                "registration_success": False,
                "error": str(e),
                "tools_registered": [],
                "registration_time": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    @activity.defn
    async def execute_tool_call(
        tool_call_data: Dict[str, Any], 
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool call with proper error handling
        
        Args:
            tool_call_data: Tool call information (name, parameters, etc.)
            context_data: Execution context (session_id, model, etc.)
            
        Returns:
            Dict with tool execution results
        """
        start_time = time.time()
        tool_name = tool_call_data.get("tool_name", "unknown")
        call_id = tool_call_data.get("id", str(uuid4()))
        
        try:
            activity.logger.info(f"Executing tool call: {tool_name} (ID: {call_id})")
            
            # Ensure tool registry is initialized
            if not tool_registry._initialized:
                tool_registry.initialize()
            
            # Create tool call object
            tool_call = ToolCall(
                id=call_id,
                tool_name=tool_name,
                parameters=tool_call_data.get("parameters", {}),
                status=ToolCallStatus.PENDING,
                timeout_seconds=tool_call_data.get("timeout_seconds")
            )
            
            # Create execution context
            context = ToolExecutionContext(
                session_id=context_data["session_id"],
                user_id=context_data.get("user_id"),
                ai_model=context_data["ai_model"],
                conversation_turn=context_data.get("conversation_turn", 1),
                metadata=context_data.get("metadata", {})
            )
            
            # Execute the tool call
            result = await tool_registry.execute_tool(tool_call, context)
            
            # Format the response
            execution_result = {
                "call_id": call_id,
                "tool_name": tool_name,
                "status": result.status,  # Already a string due to use_enum_values
                "success": result.is_success(),
                "result": result.result,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
                "execution_time_seconds": time.time() - start_time,
                "timestamp": result.timestamp.isoformat(),
                "metadata": result.metadata
            }
            
            # Status is already a string due to use_enum_values=True
            activity.logger.info(f"Tool call {tool_name} completed with status: {result.status}")
            return execution_result
            
        except ToolNotFoundError as e:
            activity.logger.error(f"Tool not found: {tool_name}")
            return {
                "call_id": call_id,
                "tool_name": tool_name,
                "status": "failed",
                "success": False,
                "result": None,
                "error": {
                    "type": "ToolNotFoundError",
                    "message": str(e),
                    "tool_name": tool_name
                },
                "execution_time_ms": 0,
                "execution_time_seconds": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {}
            }
            
        except ToolPermissionError as e:
            activity.logger.error(f"Tool permission denied: {tool_name}")
            return {
                "call_id": call_id,
                "tool_name": tool_name,
                "status": "failed",
                "success": False,
                "result": None,
                "error": {
                    "type": "ToolPermissionError",
                    "message": str(e),
                    "tool_name": tool_name
                },
                "execution_time_ms": 0,
                "execution_time_seconds": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {}
            }
            
        except Exception as e:
            activity.logger.error(f"Tool execution failed for {tool_name}: {e}")
            return {
                "call_id": call_id,
                "tool_name": tool_name,
                "status": "failed",
                "success": False,
                "result": None,
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "tool_name": tool_name
                },
                "execution_time_ms": 0,
                "execution_time_seconds": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {}
            }
    
    @staticmethod
    @activity.defn
    async def execute_multiple_tool_calls(
        tool_calls_data: List[Dict[str, Any]], 
        context_data: Dict[str, Any],
        max_concurrent: int = 3
    ) -> Dict[str, Any]:
        """
        Execute multiple tool calls concurrently with rate limiting
        
        Args:
            tool_calls_data: List of tool call information
            context_data: Execution context
            max_concurrent: Maximum concurrent executions
            
        Returns:
            Dict with all tool execution results
        """
        start_time = time.time()
        
        try:
            activity.logger.info(f"Executing {len(tool_calls_data)} tool calls concurrently (max: {max_concurrent})")
            
            import asyncio
            
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def execute_with_semaphore(tool_call_data):
                async with semaphore:
                    return await ToolCallingActivities.execute_tool_call(tool_call_data, context_data)
            
            # Execute all tool calls concurrently
            tasks = [execute_with_semaphore(tool_call) for tool_call in tool_calls_data]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            successful_calls = []
            failed_calls = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Handle exceptions from individual calls
                    failed_calls.append({
                        "call_id": tool_calls_data[i].get("id", f"call_{i}"),
                        "tool_name": tool_calls_data[i].get("tool_name", "unknown"),
                        "error": str(result),
                        "status": "failed"
                    })
                elif isinstance(result, dict) and result.get("success", False):
                    successful_calls.append(result)
                else:
                    if isinstance(result, dict):
                        failed_calls.append(result)
                    # If result is not a dict (shouldn't happen after exception handling above), skip it
            
            execution_summary = {
                "total_calls": len(tool_calls_data),
                "successful_calls": len(successful_calls),
                "failed_calls": len(failed_calls),
                "success_rate": len(successful_calls) / len(tool_calls_data) if tool_calls_data else 0,
                "results": results,
                "successful_results": successful_calls,
                "failed_results": failed_calls,
                "execution_time_seconds": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat(),
                "max_concurrent": max_concurrent
            }
            
            activity.logger.info(f"Multiple tool calls completed: {len(successful_calls)}/{len(tool_calls_data)} successful")
            return execution_summary
            
        except Exception as e:
            activity.logger.error(f"Failed to execute multiple tool calls: {e}")
            return {
                "total_calls": len(tool_calls_data),
                "successful_calls": 0,
                "failed_calls": len(tool_calls_data),
                "success_rate": 0.0,
                "results": [],
                "successful_results": [],
                "failed_results": [],
                "error": str(e),
                "execution_time_seconds": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    @activity.defn
    async def format_tool_results_for_conversation(
        tool_results: List[Dict[str, Any]], 
        turn_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format tool call results for inclusion in conversation history
        
        Args:
            tool_results: List of tool execution results
            turn_metadata: Conversation turn metadata
            
        Returns:
            Dict with formatted conversation turn data
        """
        start_time = time.time()
        
        try:
            activity.logger.info(f"Formatting {len(tool_results)} tool results for conversation history")
            
            # Format each tool call result
            formatted_tool_calls = []
            
            for result in tool_results:
                formatted_call = {
                    "tool_call_id": result.get("call_id", str(uuid4())),
                    "tool_name": result.get("tool_name", "unknown"),
                    "status": result.get("status", "unknown"),
                    "arguments": result.get("arguments", {}),
                    "result": result.get("result"),
                    "error": result.get("error"),
                    "execution_time_ms": result.get("execution_time_ms", 0),
                    "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
                    "success": result.get("success", False)
                }
                
                # Add metadata if available
                if result.get("metadata"):
                    formatted_call["metadata"] = result["metadata"]
                
                formatted_tool_calls.append(formatted_call)
            
            # Create conversation turn structure
            conversation_turn = {
                "turn_id": turn_metadata.get("turn_id", f"turn_{str(uuid4())[:8]}"),
                "turn_number": turn_metadata.get("turn_number", 1),
                "timestamp": datetime.utcnow().isoformat(),
                "messages": turn_metadata.get("messages", []),
                "tool_calls": formatted_tool_calls,
                "metadata": {
                    "session_id": turn_metadata.get("session_id"),
                    "ai_model": turn_metadata.get("ai_model"),
                    "user_id": turn_metadata.get("user_id"),
                    "tool_call_count": len(formatted_tool_calls),
                    "successful_tool_calls": len([r for r in tool_results if r.get("success", False)]),
                    "failed_tool_calls": len([r for r in tool_results if not r.get("success", False)]),
                    "total_execution_time_ms": sum(r.get("execution_time_ms", 0) for r in tool_results),
                    "formatting_time_ms": (time.time() - start_time) * 1000,
                    **turn_metadata.get("metadata", {})
                }
            }
            
            activity.logger.info(f"Formatted conversation turn with {len(formatted_tool_calls)} tool calls")
            return {
                "success": True,
                "conversation_turn": conversation_turn,
                "tool_call_count": len(formatted_tool_calls),
                "formatting_time_seconds": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            activity.logger.error(f"Failed to format tool results for conversation: {e}")
            return {
                "success": False,
                "error": str(e),
                "conversation_turn": None,
                "tool_call_count": len(tool_results),
                "formatting_time_seconds": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    @activity.defn
    async def validate_tool_call_request(tool_call_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a tool call request before execution
        
        Args:
            tool_call_data: Tool call data to validate
            
        Returns:
            Dict with validation results
        """
        start_time = time.time()
        
        try:
            tool_name = tool_call_data.get("tool_name")
            parameters = tool_call_data.get("parameters", {})
            
            activity.logger.info(f"Validating tool call request for: {tool_name}")
            
            validation_results = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "tool_name": tool_name
            }
            
            # Check if tool name is provided
            if not tool_name:
                validation_results["valid"] = False
                validation_results["errors"].append("Tool name is required")
                return validation_results
            
            # Ensure tool registry is initialized
            if not tool_registry._initialized:
                tool_registry.initialize()
            
            # Check if tool exists
            if not tool_registry.has_tool(tool_name):
                validation_results["valid"] = False
                validation_results["errors"].append(f"Tool '{tool_name}' not found in registry")
                return validation_results
            
            # Get tool and validate parameters
            try:
                tool = tool_registry.get_tool(tool_name)
                definition = tool.definition
                
                # Check required parameters
                required_params = definition.get_required_parameters()
                missing_params = []
                
                for param_name in required_params:
                    if param_name not in parameters:
                        missing_params.append(param_name)
                
                if missing_params:
                    validation_results["valid"] = False
                    validation_results["errors"].append(f"Missing required parameters: {missing_params}")
                
                # Check for unknown parameters
                valid_param_names = [param.name for param in definition.parameters]
                unknown_params = []
                
                for param_name in parameters.keys():
                    if param_name not in valid_param_names:
                        unknown_params.append(param_name)
                
                if unknown_params:
                    validation_results["warnings"].append(f"Unknown parameters will be ignored: {unknown_params}")
                
                # Validate parameter types (basic validation)
                for param in definition.parameters:
                    if param.name in parameters:
                        value = parameters[param.name]
                        # Add basic type checking here if needed
                        pass
                
            except Exception as e:
                validation_results["valid"] = False
                validation_results["errors"].append(f"Tool validation error: {str(e)}")
            
            validation_results["validation_time_seconds"] = time.time() - start_time
            validation_results["timestamp"] = datetime.utcnow().isoformat()
            
            activity.logger.info(f"Tool call validation completed for {tool_name}: {'VALID' if validation_results['valid'] else 'INVALID'}")
            return validation_results
            
        except Exception as e:
            activity.logger.error(f"Tool call validation failed: {e}")
            return {
                "valid": False,
                "errors": [f"Validation failed: {str(e)}"],
                "warnings": [],
                "tool_name": tool_call_data.get("tool_name", "unknown"),
                "validation_time_seconds": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    @activity.defn
    async def get_available_tools_for_model(model_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get list of available tools for a specific model and session
        
        Args:
            model_id: Model ID to check compatibility
            session_id: Optional session ID for permission checking
            
        Returns:
            Dict with available tools information
        """
        start_time = time.time()
        
        try:
            activity.logger.info(f"Getting available tools for model: {model_id}")
            
            # Ensure tool registry is initialized
            if not tool_registry._initialized:
                tool_registry.initialize()
            
            # Check model tool support
            model_check = await ToolCallingActivities.check_model_tool_support(model_id)
            if not model_check.get("supports_tool_calls", False):
                return {
                    "model_id": model_id,
                    "session_id": session_id,
                    "available_tools": [],
                    "tool_count": 0,
                    "model_supports_tools": False,
                    "message": f"Model {model_id} does not support tool calling",
                    "retrieval_time_seconds": time.time() - start_time,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Get compatible tools
            compatible_tools = await tool_registry.get_tools_for_model(model_id)
            
            # Filter by permissions if session provided
            available_tools = []
            for tool_name in compatible_tools:
                tool_info = {
                    "name": tool_name,
                    "description": "",
                    "parameters": [],
                    "has_permission": True
                }
                
                try:
                    # Get detailed tool info
                    tool = tool_registry.get_tool(tool_name)
                    definition = tool.definition
                    
                    tool_info.update({
                        "description": definition.description,
                        "parameters": [param.dict() for param in definition.parameters],
                        "version": definition.version,
                        "category": definition.metadata.category,
                        "timeout_seconds": definition.timeout_seconds
                    })
                    
                    # Check permissions if session provided
                    if session_id:
                        has_permission = tool_registry.check_tool_permission(
                            tool_name, session_id, "user", model_id
                        )
                        tool_info["has_permission"] = has_permission
                        
                        if not has_permission:
                            continue  # Skip tools without permission
                    
                    available_tools.append(tool_info)
                    
                except Exception as e:
                    activity.logger.warning(f"Failed to get info for tool {tool_name}: {e}")
            
            result = {
                "model_id": model_id,
                "session_id": session_id,
                "available_tools": available_tools,
                "tool_count": len(available_tools),
                "model_supports_tools": True,
                "total_compatible_tools": len(compatible_tools),
                "permission_filtered": session_id is not None,
                "retrieval_time_seconds": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            activity.logger.info(f"Retrieved {len(available_tools)} available tools for model {model_id}")
            return result
            
        except Exception as e:
            activity.logger.error(f"Failed to get available tools for model {model_id}: {e}")
            return {
                "model_id": model_id,
                "session_id": session_id,
                "available_tools": [],
                "tool_count": 0,
                "model_supports_tools": False,
                "error": str(e),
                "retrieval_time_seconds": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            } 