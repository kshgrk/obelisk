"""
Tool Execution Workflow - Specialized workflow for complex tool chains
Handles sequential tool calls, advanced retry logic, timeouts, and cancellation
"""
from datetime import timedelta
from typing import Dict, Any, Optional, List, Union
from enum import Enum

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import CancelledError, ActivityError


class ToolChainStrategy(Enum):
    """Tool chain execution strategies"""
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    CONDITIONAL = "conditional"
    DEPENDENCY_BASED = "dependency_based"


class ToolExecutionStatus(Enum):
    """Tool execution status values"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


@workflow.defn
class ToolExecutionWorkflow:
    """
    Specialized workflow for complex tool execution scenarios
    Supports tool chains, sequential execution, retries, timeouts, and cancellation
    """
    
    def __init__(self):
        # Temporal-managed state for fault tolerance
        self.execution_id: str = ""
        self.tool_chain_state: Dict[str, Any] = {}
        self.execution_status: ToolExecutionStatus = ToolExecutionStatus.PENDING
        self.current_step: int = 0
        self.tool_results: List[Dict[str, Any]] = []
        self.cancellation_requested: bool = False
        self.execution_metadata: Dict[str, Any] = {}
    
    @workflow.run
    async def run(self, 
                  execution_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complex tool chain with advanced control flow
        
        Args:
            execution_request: {
                "execution_id": str,
                "session_id": str,
                "tool_chain": List[Dict[str, Any]],
                "strategy": ToolChainStrategy,
                "config": Dict[str, Any],
                "timeout_seconds": int,
                "max_retries": int,
                "dependencies": Dict[str, List[str]]
            }
        """
        self.execution_id = execution_request.get("execution_id", f"exec_{str(workflow.uuid4())[:8]}")
        session_id = execution_request["session_id"]
        tool_chain = execution_request["tool_chain"]
        strategy = ToolChainStrategy(execution_request.get("strategy", "sequential"))
        config = execution_request.get("config", {})
        timeout_seconds = execution_request.get("timeout_seconds", 300)  # 5 minutes default
        max_retries = execution_request.get("max_retries", 3)
        dependencies = execution_request.get("dependencies", {})
        
        workflow.logger.info(f"Starting tool execution workflow: {self.execution_id} with {len(tool_chain)} tools")
        
        self.execution_status = ToolExecutionStatus.RUNNING
        self.tool_chain_state = {
            "total_tools": len(tool_chain),
            "completed_tools": 0,
            "failed_tools": 0,
            "cancelled_tools": 0,
            "strategy": strategy.value,
            "start_time": workflow.now().isoformat()
        }
        
        # Set up global timeout
        global_timeout = timedelta(seconds=timeout_seconds)
        
        try:
            # Initialize tool execution tracking
            self.execution_metadata = {
                "session_id": session_id,
                "execution_id": self.execution_id,
                "strategy": strategy.value,
                "config": config,
                "start_time": workflow.now().isoformat(),
                "tool_chain": tool_chain,
                "dependencies": dependencies
            }
            
            # Execute based on strategy
            if strategy == ToolChainStrategy.PARALLEL:
                results = await self._execute_parallel_tools(tool_chain, session_id, config, max_retries)
            elif strategy == ToolChainStrategy.SEQUENTIAL:
                results = await self._execute_sequential_tools(tool_chain, session_id, config, max_retries)
            elif strategy == ToolChainStrategy.CONDITIONAL:
                results = await self._execute_conditional_tools(tool_chain, session_id, config, max_retries)
            elif strategy == ToolChainStrategy.DEPENDENCY_BASED:
                results = await self._execute_dependency_based_tools(tool_chain, dependencies, session_id, config, max_retries)
            else:
                raise ValueError(f"Unsupported execution strategy: {strategy}")
            
            # Update final state
            self.execution_status = ToolExecutionStatus.COMPLETED
            self.tool_chain_state["end_time"] = workflow.now().isoformat()
            self.tool_chain_state["completed_tools"] = len([r for r in results if r.get("success", False)])
            self.tool_chain_state["failed_tools"] = len([r for r in results if not r.get("success", False)])
            
            # Calculate execution summary
            execution_summary = self._calculate_execution_summary(results)
            
            workflow.logger.info(f"Tool execution completed: {self.execution_id} - {execution_summary['success_rate']:.1%} success rate")
            
            return {
                "success": True,
                "execution_id": self.execution_id,
                "strategy": strategy.value,
                "status": self.execution_status.value,
                "results": results,
                "execution_summary": execution_summary,
                "tool_chain_state": self.tool_chain_state,
                "metadata": self.execution_metadata
            }
            
        except CancelledError:
            workflow.logger.warning(f"Tool execution cancelled: {self.execution_id}")
            self.execution_status = ToolExecutionStatus.CANCELLED
            return self._create_cancellation_result()
            
        except Exception as e:
            workflow.logger.error(f"Tool execution failed: {self.execution_id} - {e}")
            self.execution_status = ToolExecutionStatus.FAILED
            return self._create_error_result(str(e))
    
    async def _execute_parallel_tools(self, 
                                    tool_chain: List[Dict[str, Any]], 
                                    session_id: str,
                                    config: Dict[str, Any],
                                    max_retries: int) -> List[Dict[str, Any]]:
        """Execute tools in parallel with concurrency control"""
        workflow.logger.info(f"Executing {len(tool_chain)} tools in parallel")
        
        max_concurrent = config.get("max_concurrent", 5)
        
        # Use multiple_tool_calls activity for parallel execution
        parallel_request = {
            "tool_calls_data": tool_chain,
            "context_data": {
                "session_id": session_id,
                "ai_model": config.get("model", "default"),
                "execution_id": self.execution_id,
                "metadata": config
            },
            "max_concurrent": max_concurrent
        }
        
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=max_retries,
            backoff_coefficient=2.0,
        )
        
        parallel_result = await workflow.execute_activity(
            "execute_multiple_tool_calls",
            args=[parallel_request["tool_calls_data"], parallel_request["context_data"], max_concurrent],
            start_to_close_timeout=timedelta(seconds=config.get("timeout_per_tool", 60)),
            retry_policy=retry_policy,
        )
        
        return parallel_result.get("results", [])
    
    async def _execute_sequential_tools(self,
                                      tool_chain: List[Dict[str, Any]],
                                      session_id: str,
                                      config: Dict[str, Any],
                                      max_retries: int) -> List[Dict[str, Any]]:
        """Execute tools sequentially with dependency handling"""
        workflow.logger.info(f"Executing {len(tool_chain)} tools sequentially")
        
        results = []
        context_accumulator = {}
        
        for i, tool_call in enumerate(tool_chain):
            if self.cancellation_requested:
                break
                
            self.current_step = i + 1
            workflow.logger.info(f"Executing tool {i+1}/{len(tool_chain)}: {tool_call.get('tool_name', 'unknown')}")
            
            # Prepare execution context with accumulated results
            context_data = {
                "session_id": session_id,
                "ai_model": config.get("model", "default"),
                "execution_id": self.execution_id,
                "step_number": i + 1,
                "previous_results": context_accumulator,
                "metadata": {
                    "sequential_execution": True,
                    "total_steps": len(tool_chain),
                    **config
                }
            }
            
            # Execute single tool with retries
            tool_result = await self._execute_single_tool_with_retries(
                tool_call, context_data, max_retries, config
            )
            
            results.append(tool_result)
            
            # Update context accumulator for next tool
            if tool_result.get("success"):
                tool_name = tool_result.get("tool_name", f"tool_{i}")
                context_accumulator[tool_name] = tool_result.get("result", {})
            
            # Check for early termination conditions
            if not tool_result.get("success") and config.get("fail_fast", False):
                workflow.logger.warning(f"Sequential execution stopped due to failure at step {i+1}")
                break
        
        return results
    
    async def _execute_conditional_tools(self,
                                       tool_chain: List[Dict[str, Any]],
                                       session_id: str,
                                       config: Dict[str, Any],
                                       max_retries: int) -> List[Dict[str, Any]]:
        """Execute tools based on conditional logic"""
        workflow.logger.info(f"Executing conditional tool chain with {len(tool_chain)} tools")
        
        results = []
        context_accumulator = {}
        
        for i, tool_call in enumerate(tool_chain):
            if self.cancellation_requested:
                break
            
            # Check execution condition
            condition = tool_call.get("condition", {})
            if not self._evaluate_condition(condition, context_accumulator):
                workflow.logger.info(f"Skipping tool {i+1} due to condition: {condition}")
                continue
            
            self.current_step = i + 1
            
            # Prepare execution context
            context_data = {
                "session_id": session_id,
                "ai_model": config.get("model", "default"),
                "execution_id": self.execution_id,
                "step_number": i + 1,
                "previous_results": context_accumulator,
                "metadata": {
                    "conditional_execution": True,
                    "condition": condition,
                    **config
                }
            }
            
            # Execute tool
            tool_result = await self._execute_single_tool_with_retries(
                tool_call, context_data, max_retries, config
            )
            
            results.append(tool_result)
            
            # Update context
            if tool_result.get("success"):
                tool_name = tool_result.get("tool_name", f"tool_{i}")
                context_accumulator[tool_name] = tool_result.get("result", {})
        
        return results
    
    async def _execute_dependency_based_tools(self,
                                            tool_chain: List[Dict[str, Any]],
                                            dependencies: Dict[str, List[str]],
                                            session_id: str,
                                            config: Dict[str, Any],
                                            max_retries: int) -> List[Dict[str, Any]]:
        """Execute tools based on dependency graph"""
        workflow.logger.info(f"Executing dependency-based tool chain with {len(tool_chain)} tools")
        
        # Build execution order based on dependencies
        execution_order = self._resolve_dependencies(tool_chain, dependencies)
        results = {}
        context_accumulator = {}
        
        for batch in execution_order:
            # Execute tools in current batch (can be parallel within batch)
            batch_results = []
            
            for tool_id in batch:
                if self.cancellation_requested:
                    break
                
                tool_call = next((t for t in tool_chain if t.get("id") == tool_id), None)
                if not tool_call:
                    continue
                
                self.current_step += 1
                
                # Prepare execution context with dependency results
                context_data = {
                    "session_id": session_id,
                    "ai_model": config.get("model", "default"),
                    "execution_id": self.execution_id,
                    "tool_id": tool_id,
                    "dependency_results": context_accumulator,
                    "metadata": {
                        "dependency_based_execution": True,
                        "dependencies": dependencies.get(tool_id, []),
                        **config
                    }
                }
                
                # Execute tool
                tool_result = await self._execute_single_tool_with_retries(
                    tool_call, context_data, max_retries, config
                )
                
                batch_results.append(tool_result)
                results[tool_id] = tool_result
                
                # Update context
                if tool_result.get("success"):
                    context_accumulator[tool_id] = tool_result.get("result", {})
        
        # Convert to list format
        return list(results.values())
    
    async def _execute_single_tool_with_retries(self,
                                              tool_call: Dict[str, Any],
                                              context_data: Dict[str, Any],
                                              max_retries: int,
                                              config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool with retry logic"""
        tool_name = tool_call.get("tool_name", "unknown")
        attempt = 0
        last_error = None
        
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=config.get("retry_initial_interval", 1)),
            maximum_interval=timedelta(seconds=config.get("retry_max_interval", 10)),
            maximum_attempts=max_retries,
            backoff_coefficient=config.get("retry_backoff", 2.0),
        )
        
        while attempt <= max_retries:
            try:
                # Check for cancellation
                if self.cancellation_requested:
                    return self._create_cancelled_tool_result(tool_call)
                
                attempt += 1
                workflow.logger.info(f"Executing {tool_name} (attempt {attempt}/{max_retries + 1})")
                
                # Execute the tool
                tool_result = await workflow.execute_activity(
                    "execute_tool_call",
                    args=[tool_call, context_data],
                    start_to_close_timeout=timedelta(seconds=config.get("timeout_per_tool", 60)),
                    retry_policy=retry_policy,
                )
                
                # Check if successful
                if tool_result.get("success", False):
                    tool_result["attempt_number"] = attempt
                    return tool_result
                else:
                    last_error = tool_result.get("error", "Unknown error")
                    if attempt <= max_retries:
                        workflow.logger.warning(f"Tool {tool_name} failed on attempt {attempt}, retrying: {last_error}")
                        # Wait before retry (handled by Temporal retry policy)
                        continue
                    
            except ActivityError as e:
                last_error = str(e)
                workflow.logger.error(f"Activity error executing {tool_name} on attempt {attempt}: {e}")
                if attempt <= max_retries:
                    continue
                    
            except Exception as e:
                last_error = str(e)
                workflow.logger.error(f"Unexpected error executing {tool_name} on attempt {attempt}: {e}")
                if attempt <= max_retries:
                    continue
        
        # All retries exhausted
        workflow.logger.error(f"Tool {tool_name} failed after {max_retries + 1} attempts: {last_error}")
        return {
            "call_id": tool_call.get("id", str(workflow.uuid4())[:8]),
            "tool_name": tool_name,
            "success": False,
            "error": {
                "type": "MaxRetriesExhausted",
                "message": f"Failed after {max_retries + 1} attempts: {last_error}",
                "last_error": last_error,
                "attempts": attempt
            },
            "status": ToolExecutionStatus.FAILED.value,
            "timestamp": workflow.now().isoformat()
        }
    
    def _evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate conditional logic for tool execution"""
        if not condition:
            return True
        
        condition_type = condition.get("type", "always")
        
        if condition_type == "always":
            return True
        elif condition_type == "never":
            return False
        elif condition_type == "success":
            # Execute if previous tool succeeded
            required_tool = condition.get("tool")
            return required_tool in context
        elif condition_type == "failure":
            # Execute if previous tool failed
            required_tool = condition.get("tool")
            return required_tool not in context
        elif condition_type == "value_equals":
            # Execute if value equals condition
            tool_result = context.get(condition.get("tool", ""))
            if not tool_result:
                return False
            value_path = condition.get("path", "")
            expected_value = condition.get("value")
            actual_value = self._get_nested_value(tool_result, value_path)
            return actual_value == expected_value
        else:
            workflow.logger.warning(f"Unknown condition type: {condition_type}")
            return True
    
    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """Get nested value from object using dot notation"""
        if not path:
            return obj
        
        keys = path.split(".")
        current = obj
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def _resolve_dependencies(self, tool_chain: List[Dict[str, Any]], dependencies: Dict[str, List[str]]) -> List[List[str]]:
        """Resolve dependency graph into execution order (topological sort)"""
        # Simple topological sort implementation
        tool_ids = [tool.get("id", f"tool_{i}") for i, tool in enumerate(tool_chain)]
        in_degree = {tool_id: 0 for tool_id in tool_ids}
        
        # Calculate in-degrees
        for tool_id, deps in dependencies.items():
            if tool_id in in_degree:
                in_degree[tool_id] = len(deps)
        
        execution_order = []
        remaining_tools = set(tool_ids)
        
        while remaining_tools:
            # Find tools with no dependencies
            ready_tools = [tool_id for tool_id in remaining_tools if in_degree[tool_id] == 0]
            
            if not ready_tools:
                # Circular dependency detected, break it
                ready_tools = [next(iter(remaining_tools))]
                workflow.logger.warning("Circular dependency detected, breaking cycle")
            
            execution_order.append(ready_tools)
            
            # Remove ready tools and update in-degrees
            for tool_id in ready_tools:
                remaining_tools.remove(tool_id)
                # Update in-degrees for dependent tools
                for other_tool, deps in dependencies.items():
                    if tool_id in deps and other_tool in in_degree:
                        in_degree[other_tool] -= 1
        
        return execution_order
    
    def _calculate_execution_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate execution summary statistics"""
        total_tools = len(results)
        successful_tools = len([r for r in results if r.get("success", False)])
        failed_tools = total_tools - successful_tools
        
        total_execution_time = sum(r.get("execution_time_ms", 0) for r in results)
        
        return {
            "total_tools": total_tools,
            "successful_tools": successful_tools,
            "failed_tools": failed_tools,
            "success_rate": successful_tools / total_tools if total_tools > 0 else 0,
            "total_execution_time_ms": total_execution_time,
            "average_execution_time_ms": total_execution_time / total_tools if total_tools > 0 else 0,
            "execution_id": self.execution_id,
            "status": self.execution_status.value
        }
    
    def _create_cancellation_result(self) -> Dict[str, Any]:
        """Create result for cancelled execution"""
        return {
            "success": False,
            "execution_id": self.execution_id,
            "status": ToolExecutionStatus.CANCELLED.value,
            "error": "Execution was cancelled",
            "results": self.tool_results,
            "execution_summary": self._calculate_execution_summary(self.tool_results),
            "tool_chain_state": self.tool_chain_state,
            "metadata": self.execution_metadata
        }
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Create result for failed execution"""
        return {
            "success": False,
            "execution_id": self.execution_id,
            "status": ToolExecutionStatus.FAILED.value,
            "error": error_message,
            "results": self.tool_results,
            "execution_summary": self._calculate_execution_summary(self.tool_results),
            "tool_chain_state": self.tool_chain_state,
            "metadata": self.execution_metadata
        }
    
    def _create_cancelled_tool_result(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Create result for cancelled tool"""
        return {
            "call_id": tool_call.get("id", str(workflow.uuid4())[:8]),
            "tool_name": tool_call.get("tool_name", "unknown"),
            "success": False,
            "error": "Tool execution was cancelled",
            "status": ToolExecutionStatus.CANCELLED.value,
            "timestamp": workflow.now().isoformat()
        }
    
    @workflow.signal
    async def cancel_execution(self):
        """Signal to cancel the tool execution"""
        workflow.logger.info(f"Cancellation requested for execution: {self.execution_id}")
        self.cancellation_requested = True
        self.execution_status = ToolExecutionStatus.CANCELLED
    
    @workflow.signal
    async def update_config(self, new_config: Dict[str, Any]):
        """Signal to update execution configuration"""
        workflow.logger.info(f"Configuration update requested for execution: {self.execution_id}")
        self.execution_metadata["config"].update(new_config)
    
    @workflow.query
    def get_execution_status(self) -> Dict[str, Any]:
        """Query current execution status"""
        return {
            "execution_id": self.execution_id,
            "status": self.execution_status.value,
            "current_step": self.current_step,
            "tool_chain_state": self.tool_chain_state,
            "results_count": len(self.tool_results),
            "cancellation_requested": self.cancellation_requested
        }
    
    @workflow.query
    def get_tool_results(self) -> List[Dict[str, Any]]:
        """Query current tool execution results"""
        return self.tool_results


@workflow.defn
class ToolChainWorkflow:
    """
    Simplified workflow for basic tool chaining scenarios
    """
    
    def __init__(self):
        self.execution_state: Dict[str, Any] = {}
    
    @workflow.run
    async def run(self,
                  session_id: str,
                  tool_chain: List[Dict[str, Any]],
                  chain_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a simple tool chain
        """
        chain_id = f"chain_{str(workflow.uuid4())[:8]}"
        config = chain_config or {}
        
        # Delegate to ToolExecutionWorkflow for complex logic
        execution_request = {
            "execution_id": chain_id,
            "session_id": session_id,
            "tool_chain": tool_chain,
            "strategy": config.get("strategy", "sequential"),
            "config": config,
            "timeout_seconds": config.get("timeout_seconds", 180),
            "max_retries": config.get("max_retries", 2)
        }
        
        return await ToolExecutionWorkflow().run(execution_request) 