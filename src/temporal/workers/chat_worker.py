"""
Chat Worker - Handles chat message workflows and activities with OpenRouter integration
"""
import asyncio
import logging
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

from src.config.settings import settings
from src.temporal.client import temporal_client
from src.temporal.workflows.chat_message import ChatMessageWorkflow, StreamingChatMessageWorkflow
from src.temporal.activities.database import DatabaseActivities
from src.temporal.activities.openrouter import OpenRouterActivities
from src.temporal.activities.session import SessionActivities

# Configure logging
logging.basicConfig(level=getattr(logging, settings.logging.level))
logger = logging.getLogger(__name__)


async def start_chat_worker():
    """Start the chat worker for handling chat message workflows with OpenRouter"""
    try:
        # Connect to Temporal
        client = await temporal_client.connect()
        logger.info(f"Connected to Temporal server at {settings.temporal.server_url}")
        
        # Create worker with all necessary workflows and activities
        worker = Worker(
            client,
            task_queue=settings.temporal.task_queue,
            workflows=[
                ChatMessageWorkflow,
                StreamingChatMessageWorkflow,
            ],
            activities=[
                # Database activities
                DatabaseActivities.add_message,
                DatabaseActivities.get_session_context,
                DatabaseActivities.get_session,
                DatabaseActivities.get_session_history,
                DatabaseActivities.create_session,
                DatabaseActivities.list_sessions,
                
                # OpenRouter activities  
                OpenRouterActivities.chat_completion,
                OpenRouterActivities.stream_chat,
                OpenRouterActivities.health_check,
                OpenRouterActivities.get_models,
                
                # Session activities
                SessionActivities.check_session_inactivity,
                SessionActivities.cleanup_session_data,
                SessionActivities.log_session_completion,
                SessionActivities.get_session_metrics,
                SessionActivities.archive_inactive_sessions,
                SessionActivities.validate_session_integrity,
            ],
        )
        
        logger.info(f"Starting chat worker on task queue: {settings.temporal.task_queue}")
        logger.info("Registered workflows: ChatMessageWorkflow, StreamingChatMessageWorkflow")
        logger.info("Registered activities: Database, OpenRouter, and Session activities")
        
        # Run worker
        await worker.run()
        
    except Exception as e:
        logger.error(f"Error running chat worker: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(start_chat_worker()) 