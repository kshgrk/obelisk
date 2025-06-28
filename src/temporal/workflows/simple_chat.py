"""
Simplified Chat Workflow - Avoids temporal sandbox restrictions while using OpenRouter
"""
from datetime import timedelta
from typing import Dict, Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class SimpleChatWorkflow:
    """
    Simplified chat workflow that uses OpenRouter but avoids sandbox restrictions
    """
    
    @workflow.run
    async def run(self, 
                  session_id: str, 
                  user_message: str, 
                  streaming: bool = False) -> Dict[str, Any]:
        """
        Simple chat workflow execution using OpenRouter
        """
        workflow.logger.info(f"Processing chat message for session: {session_id}")
        
        try:
            # Configure retry policy
            retry_policy = RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=3,
            )
            
            # Step 1: Store user message
            user_msg = await workflow.execute_activity(
                "add_message",
                args=[session_id, {
                    "role": "user",
                    "content": user_message,
                    "metadata": {"streaming": streaming}
                }],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )
            
            # Step 2: Get conversation context 
            context_messages = await workflow.execute_activity(
                "get_session_context",
                args=[session_id, 10],  # max_context_messages
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )
            
            # Step 3: Prepare OpenRouter messages
            openrouter_messages = []
            for msg in context_messages["messages"]:
                openrouter_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Step 4: Get AI response from OpenRouter
            if streaming:
                ai_response = await workflow.execute_activity(
                    "stream_chat",
                    args=[{
                        "messages": openrouter_messages,
                        "temperature": 0.7,
                        "max_tokens": 1000,
                        "stream": True
                    }],
                    start_to_close_timeout=timedelta(seconds=120),
                    retry_policy=retry_policy,
                )
            else:
                ai_response = await workflow.execute_activity(
                    "chat_completion",
                    args=[{
                        "messages": openrouter_messages,
                        "temperature": 0.7,
                        "max_tokens": 1000,
                        "stream": False
                    }],
                    start_to_close_timeout=timedelta(seconds=120),
                    retry_policy=retry_policy,
                )
            
            # Step 5: Store AI response
            assistant_msg = await workflow.execute_activity(
                "add_message",
                args=[session_id, {
                    "role": "assistant",
                    "content": ai_response["content"],
                    "metadata": {
                        "streaming": streaming,
                        "model_used": ai_response.get("model"),
                        "usage": ai_response.get("usage", {}),
                        "response_time": ai_response.get("response_time")
                    }
                }],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
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
            
            # Store error message
            try:
                await workflow.execute_activity(
                    "add_message",
                    args=[session_id, {
                        "role": "assistant",
                        "content": "I apologize, but I encountered an error processing your message. Please try again.",
                        "metadata": {"error": str(e), "error_type": type(e).__name__}
                    }],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
            except:
                pass  # Don't fail if error storage fails
            
            raise


@workflow.defn 
class SimpleStreamingChatWorkflow:
    """
    Simplified streaming chat workflow
    """
    
    @workflow.run
    async def run(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """
        Streaming-specific message processing
        """
        workflow.logger.info(f"Processing streaming message for session: {session_id}")
        
        # Use the base workflow with streaming=True
        base_workflow = SimpleChatWorkflow()
        result = await base_workflow.run(session_id, user_message, streaming=True)
        
        return result 