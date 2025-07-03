"""
Optimized Chat Workflow - Uses conversation_turns structure with fault tolerance
Enhanced with comprehensive tool calling support
"""
from datetime import timedelta
from typing import Dict, Any, Optional, List

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import helper functions  
# Note: Helper functions with UUID generation moved inline to avoid sandbox restrictions


@workflow.defn
class SimpleChatWorkflow:
    """
    Optimized chat workflow using conversation_turns structure
    Provides fault-tolerant, atomic conversation processing
    Enhanced with tool calling support
    """
    
    def __init__(self):
        # Temporal-managed state for fault tolerance
        self.current_turn: Dict[str, Any] = {}
        self.session_metadata_updates: Dict[str, Any] = {}
        self.tool_execution_state: Dict[str, Any] = {}
    
    @workflow.run
    async def run(self, 
                  session_id: str, 
                  user_message: str, 
                  config_override: Optional[Dict[str, Any]] = None,
                  streaming: bool = False) -> Dict[str, Any]:
        """
        Process a complete conversation turn atomically with tool calling support
        """
        workflow.logger.info(f"Processing chat message for session: {session_id}")
        
        # Temporal state preservation - if we crash and restart, this state is preserved
        turn_id = f"turn_{str(workflow.uuid4())[:8]}"
        self.current_turn = {
            "turn_id": turn_id,
            "session_id": session_id,
            "user_message": user_message,
            "streaming": streaming,
            "status": "processing",
            "tool_execution_enabled": True
        }
        
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
            backoff_coefficient=2.0,
        )
        
        try:
            # Step 0.5: Handle model switch if requested via config_override
            if config_override and config_override.get("model"):
                requested_model = config_override["model"]
                workflow.logger.info(f"Model switch requested via config_override: {requested_model}")
                
                # Switch the model in the dynamic tool registry
                switch_result = await workflow.execute_activity(
                    "switch_session_model_dynamic",
                    args=[session_id, requested_model],
                    start_to_close_timeout=timedelta(seconds=15),
                    retry_policy=retry_policy,
                )
                
                if switch_result.get("success"):
                    workflow.logger.info(f"Model switch successful: {switch_result.get('old_model')} → {switch_result.get('new_model')}")
                else:
                    workflow.logger.warning(f"Model switch failed: {switch_result.get('error', 'Unknown error')}")
            
            # Step 0.6: Get current model from dynamic tool registry (this is the authoritative source)
            current_session_state = await workflow.execute_activity(
                "get_session_tool_state",
                args=[session_id],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=retry_policy,
            )
            
            if current_session_state.get("success") and current_session_state.get("current_model"):
                model = current_session_state["current_model"]
                workflow.logger.info(f"Using current session model from dynamic registry: {model}")
            else:
                # Fallback to default model - will be registered in dynamic registry later
                model = "deepseek/deepseek-chat-v3-0324:free"
                workflow.logger.info(f"No session state found, using default model: {model}")
            
            # Step 0.7: Initialize or update session tool state
            session_state_init = await workflow.execute_activity(
                "initialize_session_tool_state",
                args=[session_id, model],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=retry_policy,
            )
            
            workflow.logger.info(f"Session tool state initialized: {session_state_init.get('supports_tool_calls', False)} tool support")
            
            # Step 1: Get conversation context (fast - from optimized structure)
            context = await workflow.execute_activity(
                "get_conversation_context",
                args=[session_id, 5],  # Last 5 turns for context
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=retry_policy,
            )
            
            # Step 2: Prepare API parameters (model already determined from dynamic registry)
            temperature = config_override.get("temperature", 0.7) if config_override else 0.7
            max_tokens = config_override.get("max_tokens", 1000) if config_override else 1000
            
            # Check if model supports tool calling
            model_capability = await workflow.execute_activity(
                "check_model_tool_support",
                args=[model],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=retry_policy,
            )
            
            supports_tools = model_capability.get("supports_tool_calls", False)
            workflow.logger.info(f"Model {model} tool support: {supports_tools}")
            
            # Step 2.5: Register session with dynamic tool registry
            dynamic_registration = await workflow.execute_activity(
                "register_session_for_dynamic_tools",
                args=[session_id, model],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=retry_policy,
            )
            
            if dynamic_registration.get("success"):
                workflow.logger.info(f"Dynamic tool registration successful: {dynamic_registration.get('tool_count', 0)} tools available")
                
                # Step 2.6: Re-check session state after registration to get the actual current model
                # This handles cases where the model was switched in a previous message
                updated_session_state = await workflow.execute_activity(
                    "get_session_tool_state",
                    args=[session_id],
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=retry_policy,
                )
                
                if updated_session_state.get("success") and updated_session_state.get("current_model"):
                    actual_model = updated_session_state["current_model"]
                    if actual_model != model:
                        workflow.logger.info(f"Model updated from dynamic registry: {model} → {actual_model}")
                        model = actual_model
            else:
                workflow.logger.warning(f"Dynamic tool registration failed: {dynamic_registration.get('error', 'Unknown error')}")
            
            # Step 3: Register tools with OpenRouter if model supports them
            tool_schemas = []
            if supports_tools:
                tool_registration = await workflow.execute_activity(
                    "register_tools_with_openrouter",
                    args=[model, session_id],
                    start_to_close_timeout=timedelta(seconds=15),
                    retry_policy=retry_policy,
                )
                
                if tool_registration.get("registration_success"):
                    tool_schemas = tool_registration.get("tool_schemas", [])
                    workflow.logger.info(f"Registered {len(tool_schemas)} tools for model {model}")
                else:
                    workflow.logger.warning(f"Tool registration failed: {tool_registration.get('error', 'Unknown error')}")
            
            # Step 4: Call OpenRouter API with context and tools
            # Include conversation history + current user message
            openrouter_messages = self._prepare_openrouter_messages(context["messages"])
            openrouter_messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Prepare API request with tools if available
            api_request = {
                "model": model,
                "messages": openrouter_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": streaming,
                "session_id": session_id  # Add session_id for event emission
            }
            
            # Add tools to request if available
            if tool_schemas:
                api_request["tools"] = tool_schemas
                api_request["tool_choice"] = "auto"  # Let model decide when to use tools
            
            if streaming:
                ai_response = await workflow.execute_activity(
                    "stream_chat",
                    args=[api_request],
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=retry_policy,
                )
            else:
                ai_response = await workflow.execute_activity(
                    "chat_completion",
                    args=[api_request],
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=retry_policy,
                )
            
            # Step 5: Handle tool calls if present
            assistant_response = ai_response.get("content", "")
            tool_calls = ai_response.get("tool_calls", [])
            has_tool_calls = ai_response.get("has_tool_calls", False) or len(tool_calls) > 0
            
            self.tool_execution_state = {
                "has_tool_calls": has_tool_calls,
                "tool_calls": tool_calls,
                "tool_results": [],
                "final_response": assistant_response
            }
            
            if has_tool_calls and tool_calls:
                workflow.logger.info(f"Processing {len(tool_calls)} tool calls")
                
                # Step 5a: Extract tool call parameters
                tool_extraction = await workflow.execute_activity(
                    "extract_tool_call_parameters",
                    args=[tool_calls],
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=retry_policy,
                )
                
                if tool_extraction.get("success") and tool_extraction.get("extracted_calls"):
                    extracted_calls = tool_extraction["extracted_calls"]
                    
                    # Step 5b: Execute tool calls
                    tool_results = []
                    for extracted_call in extracted_calls:
                        if extracted_call.get("tool_name"):
                            tool_name = extracted_call["tool_name"]
                            
                            # Validate tool call against dynamic registry
                            validation_result = await workflow.execute_activity(
                                "validate_tool_call_for_session",
                                args=[session_id, tool_name],
                                start_to_close_timeout=timedelta(seconds=5),
                                retry_policy=retry_policy,
                            )
                            
                            if not validation_result.get("is_valid", False):
                                # Tool not available for current model/session
                                error_result = {
                                    "success": False,
                                    "tool_name": tool_name,
                                    "error": validation_result.get("validation_message", "Tool not available"),
                                    "status": "failed",
                                    "execution_time_ms": 0.0
                                }
                                tool_results.append(error_result)
                                workflow.logger.warning(f"Tool validation failed for {tool_name}: {validation_result.get('validation_message')}")
                                continue
                            
                            # Prepare execution context
                            context_data = {
                                "session_id": session_id,
                                "ai_model": model,
                                "conversation_turn": self.current_turn.get("turn_number", 1),
                                "metadata": {
                                    "streaming": streaming,
                                    "temperature": temperature,
                                    "max_tokens": max_tokens
                                }
                            }
                            
                            # Execute the tool call
                            tool_result = await workflow.execute_activity(
                                "execute_tool_call",
                                args=[extracted_call, context_data],
                                start_to_close_timeout=timedelta(seconds=30),
                                retry_policy=retry_policy,
                            )
                            
                            tool_results.append(tool_result)
                    
                    self.tool_execution_state["tool_results"] = tool_results
                    
                    # Step 5c: Inject tool results back into conversation
                    if tool_results:
                        tool_injection = await workflow.execute_activity(
                            "inject_tool_results_into_conversation",
                            args=[openrouter_messages, tool_results, ai_response.get("message", {})],
                            start_to_close_timeout=timedelta(seconds=10),
                            retry_policy=retry_policy,
                        )
                        
                        if tool_injection.get("success"):
                            updated_messages = tool_injection["updated_messages"]
                            
                            # Step 5d: Continue conversation after tools
                            continuation_request = {
                                "model": model,
                                "temperature": temperature,
                                "max_tokens": max_tokens,
                                "session_id": session_id
                            }
                            
                            final_response = await workflow.execute_activity(
                                "continue_conversation_after_tools",
                                args=[updated_messages, model, continuation_request],
                                start_to_close_timeout=timedelta(seconds=60),
                                retry_policy=retry_policy,
                            )
                            
                            if final_response.get("content"):
                                self.tool_execution_state["final_response"] = final_response["content"]
                                assistant_response = final_response["content"]
                                workflow.logger.info("Successfully continued conversation after tool execution")
                            else:
                                workflow.logger.warning("Tool continuation failed, using pre-tool response")
                        else:
                            workflow.logger.warning("Failed to inject tool results, using original response")
                else:
                    workflow.logger.warning("Failed to extract tool call parameters")
            else:
                workflow.logger.info("No tool calls detected in AI response")
            
            # Step 6: Build complete conversation turn in memory (Temporal state)
            # Generate deterministic UUIDs for turn structure
            user_msg_id = f"msg_u_{str(workflow.uuid4())[:8]}"
            resp_id = f"resp_{str(workflow.uuid4())[:8]}"
            assistant_msg_id = f"msg_a_{str(workflow.uuid4())[:8]}"
            
            # Build the complete turn structure manually to avoid UUID sandbox issues
            timestamp = workflow.now().isoformat()
            metadata = {
                "user_metadata": {
                    "source": "temporal_cli", 
                    "streaming": streaming
                },
                "assistant_metadata": {
                    "model": ai_response.get("model", model),
                    "tokens_input": ai_response.get("usage", {}).get("prompt_tokens", 0),
                    "tokens_output": ai_response.get("usage", {}).get("completion_tokens", 0),
                    "response_time_ms": ai_response.get("response_time_ms", 0),
                    "streaming": streaming,
                    "finish_reason": ai_response.get("finish_reason", "stop"),
                    "has_tool_calls": has_tool_calls,
                    "tool_calls_count": len(tool_calls),
                    "tool_execution_successful": len(self.tool_execution_state.get("tool_results", [])) > 0
                }
            }
            
            # Build generation config that was actually used
            generation_config = {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "streaming": streaming,
                "show_tool_calls": True,
                "tools_enabled": supports_tools,
                "tools_registered": len(tool_schemas)
            }
            
            # Build conversation turn with EXPLICIT field-by-field ordering
            self.current_turn = {}
            self.current_turn["turn_id"] = turn_id
            # Note: turn_number will be set correctly by the database activity
            
            # USER MESSAGE FIRST (logical conversation flow)
            self.current_turn["user_message"] = {}
            self.current_turn["user_message"]["message_id"] = user_msg_id
            self.current_turn["user_message"]["content"] = user_message
            self.current_turn["user_message"]["timestamp"] = timestamp
            self.current_turn["user_message"]["metadata"] = metadata.get("user_metadata", {})
            
            # ASSISTANT RESPONSES SECOND
            assistant_resp = {}
            assistant_resp["response_id"] = resp_id
            assistant_resp["message_id"] = assistant_msg_id
            assistant_resp["content"] = assistant_response
            assistant_resp["final_content"] = assistant_response
            assistant_resp["timestamp"] = timestamp
            assistant_resp["is_active"] = True
            
            # Add tool calls to response structure
            formatted_tool_calls = []
            if has_tool_calls and self.tool_execution_state.get("tool_results"):
                for tool_result in self.tool_execution_state["tool_results"]:
                    formatted_tool_call = {
                        "tool_call_id": tool_result.get("call_id", str(workflow.uuid4())[:8]),
                        "tool_name": tool_result.get("tool_name", "unknown"),
                        "status": tool_result.get("status", "unknown"),
                        "arguments": tool_result.get("arguments", {}),
                        "result": tool_result.get("result"),
                        "error": tool_result.get("error"),
                        "execution_time_ms": tool_result.get("execution_time_ms", 0),
                        "timestamp": tool_result.get("timestamp", timestamp),
                        "success": tool_result.get("success", False)
                    }
                    formatted_tool_calls.append(formatted_tool_call)
            
            assistant_resp["tool_calls"] = formatted_tool_calls
            assistant_resp["mcp_calls"] = []
            assistant_resp["metadata"] = {
                "generation_type": "original" if not has_tool_calls else "tool_enhanced",
                "generation_config": generation_config,
                "tool_execution_state": self.tool_execution_state,
                **metadata.get("assistant_metadata", {})
            }
            self.current_turn["assistant_responses"] = [assistant_resp]
            
            # Step 7: Atomic database save with tool analytics - all or nothing
            saved_turn = await workflow.execute_activity(
                "save_conversation_turn_with_tool_analytics",
                args=[session_id, self.current_turn],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )
            
            # Step 8: Update session metadata with statistics including tool usage
            tool_statistics = {
                "total_tool_calls": len(formatted_tool_calls),
                "successful_tool_calls": len([tc for tc in formatted_tool_calls if tc.get("success", False)]),
                "failed_tool_calls": len([tc for tc in formatted_tool_calls if not tc.get("success", False)]),
                "tool_execution_time_ms": sum(tc.get("execution_time_ms", 0) for tc in formatted_tool_calls)
            }
            
            self.session_metadata_updates = {
                "statistics": {
                    "total_tokens_input": ai_response.get("usage", {}).get("prompt_tokens", 0),
                    "total_tokens_output": ai_response.get("usage", {}).get("completion_tokens", 0),
                    "last_response_time_ms": ai_response.get("response_time_ms", 0),
                    "tool_statistics": tool_statistics
                }
            }
            
            await workflow.execute_activity(
                "update_session_metadata",
                args=[session_id, self.session_metadata_updates],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=retry_policy,
            )
            
            # Extract the actual saved turn from the enhanced response
            actual_saved_turn = saved_turn.get("saved_turn", saved_turn)
            
            # Step 9: Generate session name if this is the first message
            # Check if this is the first turn (turn_number will be 1 for first message)
            if actual_saved_turn.get("turn_number") == 1:
                try:
                    # Generate session name based on user's first message
                    session_name = await workflow.execute_activity(
                        "generate_session_name",
                        args=[user_message],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=retry_policy,
                    )
                    
                    # Update session name via API
                    await workflow.execute_activity(
                        "update_session_name_via_api",
                        args=[session_id, session_name],
                        start_to_close_timeout=timedelta(seconds=10),
                        retry_policy=retry_policy,
                    )
                    
                    workflow.logger.info(f"Generated session name '{session_name}' for session {session_id}")
                    
                except Exception as e:
                    workflow.logger.warning(f"Failed to generate session name for {session_id}: {e}")
                    # Continue without failing the entire workflow
            
            workflow.logger.info(f"Successfully processed turn {turn_id} for session {session_id} (tools: {has_tool_calls})")
            
            # Return response for immediate display including tool information
            return {
                "success": True,
                "turn_id": turn_id,
                "message_id": actual_saved_turn["assistant_responses"][0]["message_id"],
                "content": assistant_response,
                "streaming": streaming,
                "has_tool_calls": has_tool_calls,
                "tool_calls": formatted_tool_calls,
                "tool_execution_summary": {
                    "total_tools_called": len(formatted_tool_calls),
                    "successful_calls": tool_statistics["successful_tool_calls"],
                    "failed_calls": tool_statistics["failed_tool_calls"],
                    "total_execution_time_ms": tool_statistics["tool_execution_time_ms"]
                },
                "tool_statistics_update": saved_turn.get("tool_statistics_update", {}),
                "metadata": {
                    "tokens_used": ai_response.get("usage", {}),
                    "response_time_ms": ai_response.get("response_time_ms", 0),
                    "model_supports_tools": supports_tools,
                    "tools_registered": len(tool_schemas),
                    "tool_calls_processed": saved_turn.get("tool_calls_processed", 0)
                }
            }
            
        except Exception as e:
            workflow.logger.error(f"Failed to process chat message: {e}")
            
            # Return error response
            return {
                "success": False,
                "error": str(e),
                "turn_id": turn_id,
                "content": f"I apologize, but I encountered an error: {str(e)}",
                "has_tool_calls": False,
                "tool_calls": [],
                "tool_execution_summary": {
                    "total_tools_called": 0,
                    "successful_calls": 0,
                    "failed_calls": 0,
                    "total_execution_time_ms": 0
                }
            }

    def _prepare_openrouter_messages(self, context_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert context messages to OpenRouter format"""
        openrouter_messages = []
        
        for msg in context_messages:
            openrouter_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return openrouter_messages
    
    @workflow.signal
    async def switch_model(self, new_model: str) -> None:
        """Signal to switch the model mid-session"""
        workflow.logger.info(f"Received model switch signal: {new_model}")
        
        # Update current turn state
        old_model = self.current_turn.get("model", "unknown")
        self.current_turn["model_switch_requested"] = True
        self.current_turn["new_model"] = new_model
        self.current_turn["old_model"] = old_model
        
        # The actual model switch will be handled in the next message processing
        
    async def _handle_model_switch_if_requested(self, session_id: str) -> Optional[str]:
        """Handle model switch if requested"""
        if not self.current_turn.get("model_switch_requested"):
            return None
            
        new_model = self.current_turn.get("new_model")
        if not new_model:
            return None
            
        workflow.logger.info(f"Processing model switch for session {session_id} to {new_model}")
        
        try:
            # Execute dynamic model switch with session state management
            switch_result = await workflow.execute_activity(
                "update_session_model",
                args=[session_id, new_model],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=5),
                    maximum_attempts=2,
                ),
            )
            
            if switch_result.get("success"):
                workflow.logger.info(f"Model switch successful: {switch_result.get('old_model')} → {switch_result.get('new_model')}")
                workflow.logger.info(f"Tools changed: +{len(switch_result.get('tools_added', []))} -{len(switch_result.get('tools_removed', []))}")
                
                # Clear the switch request
                self.current_turn["model_switch_requested"] = False
                return new_model
            else:
                workflow.logger.error(f"Model switch failed: {switch_result.get('error', 'Unknown error')}")
                self.current_turn["model_switch_requested"] = False
                return None
                
        except Exception as e:
            workflow.logger.error(f"Exception during model switch: {e}")
            self.current_turn["model_switch_requested"] = False
            return None


@workflow.defn
class SimpleStreamingChatWorkflow:
    """
    Streaming version of chat workflow with the same fault-tolerant structure
    Enhanced with tool calling support
    """
    
    def __init__(self):
        self.current_turn: Dict[str, Any] = {}
        self.session_metadata_updates: Dict[str, Any] = {}
        self.tool_execution_state: Dict[str, Any] = {}
    
    @workflow.run
    async def run(self, 
                  session_id: str, 
                  user_message: str,
                  config_override: Optional[Dict[str, Any]] = None,
                  streaming: bool = True) -> Dict[str, Any]:
        """
        Process streaming chat with conversation_turns structure and tool calling
        """
        # Delegate to main workflow with streaming=True
        return await SimpleChatWorkflow().run(session_id, user_message, config_override, streaming=True)


@workflow.defn 
class ChatSessionWorkflow:
    """
    Long-running session workflow for managing conversation state
    Enhanced with tool calling awareness
    """
    
    def __init__(self):
        # Session-level state maintained by Temporal
        self.session_id: str = ""
        self.conversation_context: List[Dict[str, Any]] = []
        self.session_metadata: Dict[str, Any] = {}
        self.is_active: bool = True
        self.tool_usage_stats: Dict[str, Any] = {}
    
    @workflow.run
    async def run(self, session_id: str, initial_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Initialize and manage a long-running chat session with tool calling support
        This workflow can run for hours/days handling multiple messages
        """
        self.session_id = session_id
        self.session_metadata = initial_metadata or {}
        self.tool_usage_stats = {
            "total_tool_calls": 0,
            "successful_tool_calls": 0,
            "failed_tool_calls": 0,
            "tools_used": {}
        }
        
        workflow.logger.info(f"Started session workflow for {session_id} with tool calling support")
        
        # Wait for signals (messages) indefinitely
        await workflow.wait_condition(lambda: not self.is_active)
        
        workflow.logger.info(f"Session workflow ended for {session_id} (tool calls: {self.tool_usage_stats['total_tool_calls']})")
        return f"Session {session_id} completed with {self.tool_usage_stats['total_tool_calls']} tool calls"
    
    @workflow.signal
    async def new_message(self, user_message: str, streaming: bool = False):
        """
        Signal handler for new messages in the session with tool calling support
        Processes message and maintains conversation state
        """
        if not self.is_active:
            return
        
        workflow.logger.info(f"Received message in session {self.session_id}")
        
        # Process the message using the enhanced fault-tolerant logic
        result = await SimpleChatWorkflow().run(self.session_id, user_message, None, streaming)
        
        # Update in-memory context and tool usage stats
        if result.get("success"):
            # Add to local context cache (Redis will be added later)
            self.conversation_context.append({
                "role": "user",
                "content": user_message,
                "message_id": f"user_{len(self.conversation_context)}"
            })
            
            assistant_message = {
                "role": "assistant", 
                "content": result.get("content", ""),
                "message_id": result.get("message_id", ""),
                "has_tool_calls": result.get("has_tool_calls", False),
                "tool_calls": result.get("tool_calls", [])
            }
            self.conversation_context.append(assistant_message)
            
            # Update tool usage statistics
            if result.get("has_tool_calls"):
                tool_summary = result.get("tool_execution_summary", {})
                self.tool_usage_stats["total_tool_calls"] += tool_summary.get("total_tools_called", 0)
                self.tool_usage_stats["successful_tool_calls"] += tool_summary.get("successful_calls", 0)
                self.tool_usage_stats["failed_tool_calls"] += tool_summary.get("failed_calls", 0)
                
                # Track individual tool usage
                for tool_call in result.get("tool_calls", []):
                    tool_name = tool_call.get("tool_name", "unknown")
                    if tool_name not in self.tool_usage_stats["tools_used"]:
                        self.tool_usage_stats["tools_used"][tool_name] = {
                            "count": 0,
                            "successes": 0,
                            "failures": 0
                        }
                    self.tool_usage_stats["tools_used"][tool_name]["count"] += 1
                    if tool_call.get("success", False):
                        self.tool_usage_stats["tools_used"][tool_name]["successes"] += 1
                    else:
                        self.tool_usage_stats["tools_used"][tool_name]["failures"] += 1
            
            # Keep context window manageable (last 20 messages)
            if len(self.conversation_context) > 20:
                self.conversation_context = self.conversation_context[-20:]
    
    @workflow.signal
    async def end_session(self):
        """Signal to end the session"""
        self.is_active = False
        workflow.logger.info(f"Ending session {self.session_id} (tool calls: {self.tool_usage_stats['total_tool_calls']})")
    
    @workflow.query
    def get_session_status(self) -> Dict[str, Any]:
        """Query current session status including tool usage"""
        return {
            "session_id": self.session_id,
            "is_active": self.is_active,
            "context_size": len(self.conversation_context),
            "metadata": self.session_metadata,
            "tool_usage_stats": self.tool_usage_stats
        } 