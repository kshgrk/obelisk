"""
Optimized Chat Worker - Handles conversation_turns workflows with fault tolerance
"""
import asyncio
import logging
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

from src.temporal.workflows.simple_chat import SimpleChatWorkflow, SimpleStreamingChatWorkflow, ChatSessionWorkflow
from src.temporal.activities.database import DatabaseActivities
from src.temporal.activities.openrouter import OpenRouterActivities

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start_optimized_chat_worker():
    """Start the optimized chat worker with conversation_turns support"""
    try:
        # Connect to Temporal
        client = await Client.connect("localhost:7233")
        logger.info("Connected to Temporal server")
        
        # Create worker with all activities and workflows
        worker = Worker(
            client,
            task_queue="obelisk-task-queue",
            workflows=[
                SimpleChatWorkflow,
                SimpleStreamingChatWorkflow,
                ChatSessionWorkflow,  # Future long-running session workflow
            ],
            activities=[
                # New optimized database activities
                DatabaseActivities.create_session,
                DatabaseActivities.save_conversation_turn,
                DatabaseActivities.get_conversation_context,
                DatabaseActivities.get_full_conversation,
                DatabaseActivities.update_session_metadata,
                DatabaseActivities.get_session_info,
                
                # Legacy compatibility activities
                DatabaseActivities.add_message,
                DatabaseActivities.get_session_context,
                
                # OpenRouter activities  
                OpenRouterActivities.chat_completion,
                OpenRouterActivities.stream_chat,
                OpenRouterActivities.health_check,
                OpenRouterActivities.get_models,
            ],
        )
        
        logger.info("Starting optimized chat worker with conversation_turns support...")
        logger.info("Registered workflows: SimpleChatWorkflow, SimpleStreamingChatWorkflow, ChatSessionWorkflow")
        logger.info("Registered activities: Optimized Database and OpenRouter activities")
        
        await worker.run()
        
    except Exception as e:
        logger.error(f"Failed to start worker: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(start_optimized_chat_worker()) 