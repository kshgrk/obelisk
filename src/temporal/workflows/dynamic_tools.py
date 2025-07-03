"""
Dynamic Tool Management Workflow
Simple workflow for executing dynamic tool activities from API endpoints
"""
from datetime import timedelta
from typing import Dict, Any, Optional, List

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class DynamicToolManagementWorkflow:
    """Simple workflow for executing dynamic tool management activities"""
    
    @workflow.run
    async def run(self, activity_name: str, args: List[Any]) -> Dict[str, Any]:
        """Execute a dynamic tool activity and return the result"""
        
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=5),
            maximum_attempts=3,
        )
        
        try:
            result = await workflow.execute_activity(
                activity_name,
                args=args,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )
            
            return result
            
        except Exception as e:
            workflow.logger.error(f"Failed to execute activity {activity_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "activity_name": activity_name
            } 