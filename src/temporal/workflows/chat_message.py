"""
Chat Message Workflow - Short-running workflow for processing individual chat messages
"""
from datetime import timedelta
from typing import List, Dict, Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

from src.models.chat import ChatMessage, ChatMessageCreate, MessageRole, OpenRouterMessage
from src.temporal.activities.database import DatabaseActivities
from src.temporal.activities.openrouter import OpenRouterActivities
from src.config.settings import settings


@workflow.defn
class ChatMessageWorkflow:
    """
    Short-running workflow that handles individual message processing.
    This includes context retrieval, OpenRouter API calls, and response storage.
    """
    
    def __init__(self):
        # Configure retry policy for activities
        self.retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=settings.temporal.retry_attempts,
        )
    
    @workflow.run
    async def run(self, 
                  session_id: str, 
                  user_message: str, 
                  streaming: bool = False,
                  temperature: Optional[float] = None,
                  max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        Main workflow execution - processes a single chat message
        """
        workflow.logger.info(f"Processing message for session: {session_id}")
        
        try:
            # Step 1: Store user message
            user_msg = await workflow.execute_activity(
                DatabaseActivities.add_message,
                args=[session_id, {
                    "role": MessageRole.USER.value,
                    "content": user_message,
                    "metadata": {"streaming": streaming}
                }],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
            
            # Step 2: Get conversation context
            context_messages = await workflow.execute_activity(
                DatabaseActivities.get_session_context,
                args=[session_id, settings.chat.max_context_messages],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
            
            # Step 3: Prepare OpenRouter request
            openrouter_messages = self._prepare_openrouter_messages(context_messages)
            
            # Step 4: Get AI response
            if streaming:
                # Handle streaming response
                ai_response = await workflow.execute_activity(
                    OpenRouterActivities.stream_chat,
                    args=[{
                        "messages": openrouter_messages,
                        "temperature": temperature or settings.openrouter.temperature,
                        "max_tokens": max_tokens or settings.openrouter.max_tokens,
                        "stream": True
                    }],
                    start_to_close_timeout=timedelta(seconds=120),
                    retry_policy=self.retry_policy,
                )
            else:
                # Handle non-streaming response
                ai_response = await workflow.execute_activity(
                    OpenRouterActivities.chat_completion,
                    args=[{
                        "messages": openrouter_messages,
                        "temperature": temperature or settings.openrouter.temperature,
                        "max_tokens": max_tokens or settings.openrouter.max_tokens,
                        "stream": False
                    }],
                    start_to_close_timeout=timedelta(seconds=120),
                    retry_policy=self.retry_policy,
                )
            
            # Step 5: Store AI response
            assistant_msg = await workflow.execute_activity(
                DatabaseActivities.add_message,
                args=[session_id, {
                    "role": MessageRole.ASSISTANT.value,
                    "content": ai_response["content"],
                    "metadata": {
                        "streaming": streaming,
                        "model_used": ai_response.get("model"),
                        "usage": ai_response.get("usage", {}),
                        "response_time": ai_response.get("response_time")
                    }
                }],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=self.retry_policy,
            )
            
            workflow.logger.info(f"Successfully processed message for session: {session_id}")
            
            return {
                "session_id": session_id,
                "user_message_id": user_msg["id"],
                "assistant_message_id": assistant_msg["id"],
                "content": ai_response["content"],
                "streaming": streaming,
                "metadata": assistant_msg["metadata"]
            }
            
        except Exception as e:
            workflow.logger.error(f"Error processing message for session {session_id}: {e}")
            
            # Store error message for user feedback
            await workflow.execute_activity(
                DatabaseActivities.add_message,
                args=[session_id, {
                    "role": MessageRole.ASSISTANT.value,
                    "content": "I apologize, but I encountered an error processing your message. Please try again.",
                    "metadata": {"error": str(e), "error_type": type(e).__name__}
                }],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=1),  # Don't retry error storage
            )
            
            raise  # Re-raise for workflow failure handling
    
    def _prepare_openrouter_messages(self, context_messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Convert database messages to OpenRouter format"""
        openrouter_messages = []
        
        for msg in context_messages:
            openrouter_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return openrouter_messages


@workflow.defn
class StreamingChatMessageWorkflow(ChatMessageWorkflow):
    """
    Specialized workflow for handling streaming chat messages with real-time updates
    """
    
    @workflow.run
    async def run(self, 
                  session_id: str, 
                  user_message: str, 
                  temperature: Optional[float] = None,
                  max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        Streaming-specific message processing with real-time signal updates
        """
        workflow.logger.info(f"Processing streaming message for session: {session_id}")
        
        # Use parent class with streaming=True
        result = await super().run(
            session_id=session_id,
            user_message=user_message,
            streaming=True,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Send completion signal to session workflow
        await self._notify_session_workflow(session_id, result)
        
        return result
    
    async def _notify_session_workflow(self, session_id: str, result: Dict[str, Any]):
        """Notify the session workflow about message completion"""
        try:
            # This would send a signal to the ChatSessionWorkflow
            # In a real implementation, you'd look up the workflow by session_id
            workflow.logger.info(f"Message processing completed for session: {session_id}")
            
        except Exception as e:
            workflow.logger.error(f"Failed to notify session workflow: {e}")
            # Don't fail the main workflow for notification issues 