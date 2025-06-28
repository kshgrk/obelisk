"""
Simple Chat Worker - Basic version for testing Temporal setup
"""
import asyncio
import logging
from datetime import timedelta
from typing import Dict, Any
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.common import RetryPolicy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@activity.defn
async def simple_echo_activity(message: str) -> str:
    """Simple activity that echoes a message"""
    activity.logger.info(f"Echo activity received: {message}")
    return f"Echo: {message}"


@workflow.defn
class SimpleEchoWorkflow:
    """Simple workflow for testing"""
    
    @workflow.run
    async def run(self, message: str) -> Dict[str, Any]:
        """Simple workflow that echoes a message via activity"""
        workflow.logger.info(f"Processing echo workflow for: {message}")
        
        result = await workflow.execute_activity(
            simple_echo_activity,
            args=[message],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        return {
            "input": message,
            "output": result,
            "workflow_id": workflow.info().workflow_id
        }


async def start_simple_worker():
    """Start the simple worker for testing"""
    try:
        # Connect to Temporal
        client = await Client.connect("localhost:7233")
        
        # Create worker
        worker = Worker(
            client,
            task_queue="obelisk-task-queue",
            workflows=[SimpleEchoWorkflow],
            activities=[simple_echo_activity],
        )
        
        logger.info("Starting Simple Worker on task queue: obelisk-task-queue")
        await worker.run()
        
    except KeyboardInterrupt:
        logger.info("Simple Worker stopped by user")
    except Exception as e:
        logger.error(f"Simple Worker error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(start_simple_worker()) 