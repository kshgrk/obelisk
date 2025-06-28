"""
Simple Chat Worker - Handles both echo and chat workflows without complex dependencies
"""
import asyncio
import logging
from datetime import timedelta
from typing import Dict, Any
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.common import RetryPolicy

from src.temporal.workers.simple_worker import SimpleEchoWorkflow, simple_echo_activity
from src.temporal.workflows.simple_chat import SimpleChatWorkflow, SimpleStreamingChatWorkflow
from src.temporal.activities.database import DatabaseActivities
from src.temporal.activities.openrouter import OpenRouterActivities

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start_simple_chat_worker():
    """Start the simple chat worker for handling both echo and chat workflows"""
    try:
        # Connect to Temporal
        client = await Client.connect("localhost:7233")
        logger.info("Connected to Temporal server")
        
        # Create worker with workflows and activities
        worker = Worker(
            client,
            task_queue="obelisk-task-queue",
            workflows=[
                SimpleEchoWorkflow,
                SimpleChatWorkflow,
                SimpleStreamingChatWorkflow,
            ],
            activities=[
                # Simple activities
                simple_echo_activity,
                
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
            ],
        )
        
        logger.info("Starting simple chat worker on task queue: obelisk-task-queue")
        logger.info("Registered workflows: SimpleEcho, SimpleChat, SimpleStreamingChat")
        logger.info("Registered activities: Database and OpenRouter activities")
        
        # Run worker
        await worker.run()
        
    except Exception as e:
        logger.error(f"Error running simple chat worker: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(start_simple_chat_worker()) 