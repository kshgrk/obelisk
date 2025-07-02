"""
Optimized Chat Workflow - Uses conversation_turns structure with fault tolerance
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
    """
    
    def __init__(self):
        # Temporal-managed state for fault tolerance
        self.current_turn: Dict[str, Any] = {}
        self.session_metadata_updates: Dict[str, Any] = {}
    
    @workflow.run
    async def run(self, 
                  session_id: str, 
                  user_message: str, 
                  config_override: Optional[Dict[str, Any]] = None,
                  streaming: bool = False) -> Dict[str, Any]:
        """
        Process a complete conversation turn atomically
        """
        workflow.logger.info(f"Processing chat message for session: {session_id}")
        
        # Temporal state preservation - if we crash and restart, this state is preserved
        turn_id = f"turn_{str(workflow.uuid4())[:8]}"
        self.current_turn = {
            "turn_id": turn_id,
            "session_id": session_id,
            "user_message": user_message,
            "streaming": streaming,
            "status": "processing"
        }
        
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
            backoff_coefficient=2.0,
        )
        
        try:
            # Step 1: Get conversation context (fast - from optimized structure)
            context = await workflow.execute_activity(
                "get_conversation_context",
                args=[session_id, 5],  # Last 5 turns for context
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=retry_policy,
            )
            
            # Step 2: Call OpenRouter API with context
            # Include conversation history + current user message
            openrouter_messages = self._prepare_openrouter_messages(context["messages"])
            openrouter_messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Use config_override for model or fallback to default
            model = config_override.get("model", "deepseek/deepseek-chat-v3-0324:free") if config_override else "deepseek/deepseek-chat-v3-0324:free"
            temperature = config_override.get("temperature", 0.7) if config_override else 0.7
            max_tokens = config_override.get("max_tokens", 1000) if config_override else 1000
            
            if streaming:
                ai_response = await workflow.execute_activity(
                    "stream_chat",
                    args=[{
                        "model": model,
                        "messages": openrouter_messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True,
                        "session_id": session_id  # Add session_id for event emission
                    }],
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=retry_policy,
                )
            else:
                ai_response = await workflow.execute_activity(
                    "chat_completion",
                    args=[{
                        "model": model, 
                        "messages": openrouter_messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": False,
                        "session_id": session_id  # Add session_id for event emission
                    }],
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=retry_policy,
                )
            
            # Step 3: Build complete conversation turn in memory (Temporal state)
            assistant_response = ai_response.get("content", "")
            tool_calls = []  # Future: will be populated by tool execution
            
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
                    "finish_reason": ai_response.get("finish_reason", "stop")
                }
            }
            
            # Build generation config that was actually used
            generation_config = {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "streaming": streaming,
                "show_tool_calls": True  # Default for now
            }
            
            # Build conversation turn with EXPLICIT field-by-field ordering
            self.current_turn = {}
            self.current_turn["turn_id"] = turn_id
            self.current_turn["turn_number"] = 1  # Will be set correctly when saved to database
            
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
            assistant_resp["tool_calls"] = tool_calls
            assistant_resp["mcp_calls"] = []
            assistant_resp["metadata"] = {
                "generation_type": "original",
                "generation_config": generation_config,
                **metadata.get("assistant_metadata", {})
            }
            self.current_turn["assistant_responses"] = [assistant_resp]
            
            # Step 4: Atomic database save - all or nothing
            saved_turn = await workflow.execute_activity(
                "save_conversation_turn",
                args=[session_id, self.current_turn],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )
            
            # Step 5: Update session metadata with statistics
            self.session_metadata_updates = {
                "statistics": {
                    "total_tokens_input": ai_response.get("usage", {}).get("prompt_tokens", 0),
                    "total_tokens_output": ai_response.get("usage", {}).get("completion_tokens", 0),
                    "last_response_time_ms": ai_response.get("response_time_ms", 0)
                }
            }
            
            await workflow.execute_activity(
                "update_session_metadata",
                args=[session_id, self.session_metadata_updates],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=retry_policy,
            )
            
            workflow.logger.info(f"Successfully processed turn {turn_id} for session {session_id}")
            
            # Return response for immediate display
            return {
                "success": True,
                "turn_id": turn_id,
                "message_id": saved_turn["assistant_responses"][0]["message_id"],
                "content": assistant_response,
                "streaming": streaming,
                "metadata": {
                    "tokens_used": ai_response.get("usage", {}),
                    "response_time_ms": ai_response.get("response_time_ms", 0)
                }
            }
            
        except Exception as e:
            workflow.logger.error(f"Failed to process chat message: {e}")
            
            # Return error response
            return {
                "success": False,
                "error": str(e),
                "turn_id": turn_id,
                "content": f"I apologize, but I encountered an error: {str(e)}"
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


@workflow.defn
class SimpleStreamingChatWorkflow:
    """
    Streaming version of chat workflow with the same fault-tolerant structure
    """
    
    def __init__(self):
        self.current_turn: Dict[str, Any] = {}
        self.session_metadata_updates: Dict[str, Any] = {}
    
    @workflow.run
    async def run(self, 
                  session_id: str, 
                  user_message: str,
                  config_override: Optional[Dict[str, Any]] = None,
                  streaming: bool = True) -> Dict[str, Any]:
        """
        Process streaming chat with conversation_turns structure
        """
        # Delegate to main workflow with streaming=True
        return await SimpleChatWorkflow().run(session_id, user_message, config_override, streaming=True)


@workflow.defn 
class ChatSessionWorkflow:
    """
    Long-running session workflow for managing conversation state
    Future implementation for Redis + Temporal architecture
    """
    
    def __init__(self):
        # Session-level state maintained by Temporal
        self.session_id: str = ""
        self.conversation_context: List[Dict[str, Any]] = []
        self.session_metadata: Dict[str, Any] = {}
        self.is_active: bool = True
    
    @workflow.run
    async def run(self, session_id: str, initial_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Initialize and manage a long-running chat session
        This workflow can run for hours/days handling multiple messages
        """
        self.session_id = session_id
        self.session_metadata = initial_metadata or {}
        
        workflow.logger.info(f"Started session workflow for {session_id}")
        
        # Wait for signals (messages) indefinitely
        await workflow.wait_condition(lambda: not self.is_active)
        
        workflow.logger.info(f"Session workflow ended for {session_id}")
        return f"Session {session_id} completed"
    
    @workflow.signal
    async def new_message(self, user_message: str, streaming: bool = False):
        """
        Signal handler for new messages in the session
        Processes message and maintains conversation state
        """
        if not self.is_active:
            return
        
        workflow.logger.info(f"Received message in session {self.session_id}")
        
        # Process the message using the same fault-tolerant logic
        result = await SimpleChatWorkflow().run(self.session_id, user_message, None, streaming)
        
        # Update in-memory context (for fast access)
        if result.get("success"):
            # Add to local context cache (Redis will be added later)
            self.conversation_context.append({
                "role": "user",
                "content": user_message,
                "message_id": f"user_{len(self.conversation_context)}"
            })
            self.conversation_context.append({
                "role": "assistant", 
                "content": result.get("content", ""),
                "message_id": result.get("message_id", "")
            })
            
            # Keep context window manageable (last 20 messages)
            if len(self.conversation_context) > 20:
                self.conversation_context = self.conversation_context[-20:]
    
    @workflow.signal
    async def end_session(self):
        """Signal to end the session"""
        self.is_active = False
        workflow.logger.info(f"Ending session {self.session_id}")
    
    @workflow.query
    def get_session_status(self) -> Dict[str, Any]:
        """Query current session status"""
        return {
            "session_id": self.session_id,
            "is_active": self.is_active,
            "context_size": len(self.conversation_context),
            "metadata": self.session_metadata
        } 