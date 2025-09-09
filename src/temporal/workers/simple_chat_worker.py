"""
Optimized Chat Worker - Handles conversation_turns workflows with fault tolerance
"""
import asyncio
import logging
import sys
import os
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add the project root to Python path for direct execution
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

from src.temporal.workflows.simple_chat import SimpleChatWorkflow, SimpleStreamingChatWorkflow, ChatSessionWorkflow
from src.temporal.workflows.tool_execution import ToolExecutionWorkflow, ToolChainWorkflow
from src.temporal.workflows.dynamic_tools import DynamicToolManagementWorkflow
from src.temporal.activities.database import DatabaseActivities
from src.temporal.activities.openrouter import OpenRouterActivities
from src.temporal.activities.tools import ToolCallingActivities
from src.temporal.activities.dynamic_tools import DynamicToolActivities
from src.temporal.activities.session import generate_session_name, update_session_name_in_db, update_session_name_via_api
from src.temporal.activities.session_state import (
    initialize_session_tool_state, update_session_model, get_session_tool_availability,
    update_session_tool_configuration, refresh_tool_availability_cache,
    record_tool_execution_for_session, get_session_tool_statistics,
    cleanup_expired_session_states
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start_optimized_chat_worker():
    """Start the optimized chat worker with conversation_turns support and SSE event emission"""
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
                ToolExecutionWorkflow,  # Advanced tool execution workflow
                ToolChainWorkflow,     # Simple tool chaining workflow
                DynamicToolManagementWorkflow,  # Dynamic tool management workflow
            ],
            activities=[
                # New optimized database activities
                DatabaseActivities.create_session,
                DatabaseActivities.create_session_with_id,
                DatabaseActivities.save_conversation_turn,
                DatabaseActivities.save_conversation_turn_with_tool_analytics,
                DatabaseActivities.update_tool_statistics_for_session,
                DatabaseActivities.get_session_tool_statistics,
                DatabaseActivities.get_global_tool_analytics,
                DatabaseActivities.get_conversation_context,
                DatabaseActivities.get_full_conversation,
                DatabaseActivities.update_session_metadata,
                DatabaseActivities.get_session_info,
                
                # Legacy compatibility activities (disabled)
                DatabaseActivities.add_message,
                
                # OpenRouter activities  
                OpenRouterActivities.chat_completion,
                OpenRouterActivities.stream_chat,
                OpenRouterActivities.health_check,
                OpenRouterActivities.get_models,
                OpenRouterActivities.extract_tool_call_parameters,
                OpenRouterActivities.inject_tool_results_into_conversation,
                OpenRouterActivities.continue_conversation_after_tools,
                
                # Tool Calling activities
                ToolCallingActivities.check_model_tool_support,
                ToolCallingActivities.register_tools_with_openrouter,
                ToolCallingActivities.execute_tool_call,
                ToolCallingActivities.execute_multiple_tool_calls,
                ToolCallingActivities.format_tool_results_for_conversation,
                ToolCallingActivities.validate_tool_call_request,
                ToolCallingActivities.get_available_tools_for_model,
                
                # Dynamic Tool Registration activities
                DynamicToolActivities.register_session_for_dynamic_tools,
                DynamicToolActivities.switch_session_model_dynamic,
                DynamicToolActivities.validate_tool_call_for_session,
                DynamicToolActivities.get_session_tools,
                DynamicToolActivities.suggest_model_switch_for_tools,
                DynamicToolActivities.get_tool_compatibility_matrix,
                DynamicToolActivities.get_session_tool_state,
                DynamicToolActivities.get_model_change_history,
                DynamicToolActivities.cleanup_session_tools,
                
                # Session activities
                generate_session_name,
                update_session_name_in_db,
                update_session_name_via_api,
                
                # Session State Management activities
                initialize_session_tool_state,
                update_session_model,
                get_session_tool_availability,
                update_session_tool_configuration,
                refresh_tool_availability_cache,
                record_tool_execution_for_session,
                # get_session_tool_statistics, # Duplicate - already registered from DatabaseActivities
                cleanup_expired_session_states,
            ],
        )
        
        logger.info("Starting optimized chat worker with conversation_turns support and tool calling...")
        logger.info("Registered workflows: SimpleChatWorkflow, SimpleStreamingChatWorkflow, ChatSessionWorkflow, ToolExecutionWorkflow, ToolChainWorkflow")
        logger.info("Registered activities: Optimized Database, OpenRouter, and Tool Calling activities")
        logger.info("✅ Event emission is handled by OpenRouter activities → API router SSE system")
        logger.info("✅ Tool calling support: Advanced tool execution workflows with retries, timeouts, and cancellation")
        logger.info("✅ Dynamic tool registration: Model switching and tool availability management")
        
        await worker.run()
        
    except Exception as e:
        logger.error(f"Failed to start worker: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(start_optimized_chat_worker()) 