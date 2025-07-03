"""
Base tool class and result handling for the tool calling system
"""
import time
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type, List, Callable, Awaitable, TYPE_CHECKING
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, field
from collections import defaultdict

if TYPE_CHECKING:
    from .registry import ToolRegistry

from .schemas import (
    ToolDefinition, ToolParameter, ToolCall, ToolCallResult, 
    ToolCallStatus, ToolExecutionContext
)
from .exceptions import (
    ToolError, ToolExecutionError, ToolValidationError, 
    ToolTimeoutError, ToolConfigurationError
)

logger = logging.getLogger(__name__)


@dataclass
class ToolMetrics:
    """Utility class for tracking tool performance metrics"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    cancelled_calls: int = 0
    total_execution_time_ms: float = 0.0
    min_execution_time_ms: float = float('inf')
    max_execution_time_ms: float = 0.0
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    recent_executions: List[float] = field(default_factory=list)
    
    def record_execution(self, result: ToolCallResult) -> None:
        """Record execution metrics from a tool call result"""
        self.total_calls += 1
        
        # Track execution time
        execution_time = result.execution_time_ms
        self.total_execution_time_ms += execution_time
        self.min_execution_time_ms = min(self.min_execution_time_ms, execution_time)
        self.max_execution_time_ms = max(self.max_execution_time_ms, execution_time)
        
        # Keep recent executions for trend analysis (last 10)
        self.recent_executions.append(execution_time)
        if len(self.recent_executions) > 10:
            self.recent_executions.pop(0)
        
        # Track status (status is already a string due to use_enum_values=True)
        if result.status == "completed":
            self.successful_calls += 1
        elif result.status == "failed":
            self.failed_calls += 1
            if result.error:
                error_type = result.error.get('type', 'Unknown')
                self.error_counts[error_type] += 1
        elif result.status == "timeout":
            self.timeout_calls += 1
        elif result.status == "cancelled":
            self.cancelled_calls += 1
    
    def get_success_rate(self) -> float:
        """Get success rate as percentage"""
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100
    
    def get_average_execution_time(self) -> float:
        """Get average execution time in milliseconds"""
        if self.total_calls == 0:
            return 0.0
        return self.total_execution_time_ms / self.total_calls
    
    def get_recent_average(self) -> float:
        """Get average of recent executions"""
        if not self.recent_executions:
            return 0.0
        return sum(self.recent_executions) / len(self.recent_executions)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "timeout_calls": self.timeout_calls,
            "cancelled_calls": self.cancelled_calls,
            "success_rate_percent": self.get_success_rate(),
            "average_execution_time_ms": self.get_average_execution_time(),
            "recent_average_execution_time_ms": self.get_recent_average(),
            "min_execution_time_ms": self.min_execution_time_ms if self.min_execution_time_ms != float('inf') else 0,
            "max_execution_time_ms": self.max_execution_time_ms,
            "error_counts": dict(self.error_counts)
        }


class ToolExecutor:
    """Utility class for managing tool execution workflows"""
    
    def __init__(self, registry: Optional['ToolRegistry'] = None):
        from .registry import tool_registry
        self.registry = registry or tool_registry
        self._metrics: Dict[str, ToolMetrics] = defaultdict(ToolMetrics)
        self._middleware: List[Callable[[ToolCall, ToolExecutionContext], Awaitable[Optional[ToolCall]]]] = []
        self._result_processors: List[Callable[[ToolCallResult], Awaitable[ToolCallResult]]] = []
    
    def add_middleware(self, middleware: Callable[[ToolCall, ToolExecutionContext], Awaitable[Optional[ToolCall]]]) -> None:
        """Add middleware that processes tool calls before execution"""
        self._middleware.append(middleware)
    
    def add_result_processor(self, processor: Callable[[ToolCallResult], Awaitable[ToolCallResult]]) -> None:
        """Add result processor that modifies results after execution"""
        self._result_processors.append(processor)
    
    async def execute_with_retry(self, 
                                tool_call: ToolCall, 
                                context: ToolExecutionContext,
                                max_retries: int = 3,
                                retry_delay: float = 1.0) -> ToolCallResult:
        """Execute a tool call with retry logic"""
        last_result = None
        
        for attempt in range(max_retries + 1):
            try:
                result = await self.execute(tool_call, context)
                
                # Record metrics
                self._metrics[tool_call.tool_name].record_execution(result)
                
                if result.is_success():
                    return result
                
                last_result = result
                
                # Don't retry if it's a validation error or configuration error
                if result.error and result.error.get('type') in ['ToolValidationError', 'ToolConfigurationError']:
                    break
                
                if attempt < max_retries:
                    logger.warning(f"Tool '{tool_call.tool_name}' failed (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                
            except Exception as e:
                logger.error(f"Unexpected error during tool execution (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    # Create error result for final attempt
                    last_result = ToolCallResult(
                        call_id=tool_call.id,
                        tool_name=tool_call.tool_name,
                        status=ToolCallStatus.FAILED,
                        result=None,
                        error={
                            "message": f"Execution failed after {max_retries} retries: {str(e)}",
                            "type": type(e).__name__
                        },
                        execution_time_ms=0.0
                    )
                    self._metrics[tool_call.tool_name].record_execution(last_result)
                else:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
        
        return last_result or ToolCallResult(
            call_id=tool_call.id,
            tool_name=tool_call.tool_name,
            status=ToolCallStatus.FAILED,
            result=None,
            error={"message": "Failed to execute after retries", "type": "ToolExecutionError"},
            execution_time_ms=0.0
        )
    
    async def execute(self, tool_call: ToolCall, context: ToolExecutionContext) -> ToolCallResult:
        """Execute a tool call with middleware and result processing"""
        # Apply middleware
        processed_call = tool_call
        for middleware in self._middleware:
            processed_result = await middleware(processed_call, context)
            if processed_result is not None:
                processed_call = processed_result
        
        # Execute the tool
        result = await self.registry.execute_tool(processed_call, context)
        
        # Apply result processors
        processed_result = result
        for processor in self._result_processors:
            processed_result = await processor(processed_result)
        
        return processed_result
    
    async def execute_parallel(self, 
                              tool_calls: List[ToolCall], 
                              context: ToolExecutionContext,
                              max_concurrent: int = 5) -> List[ToolCallResult]:
        """Execute multiple tool calls in parallel with concurrency control"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_with_semaphore(tool_call: ToolCall) -> ToolCallResult:
            async with semaphore:
                return await self.execute(tool_call, context)
        
        tasks = [execute_with_semaphore(call) for call in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = ToolCallResult(
                    call_id=tool_calls[i].id,
                    tool_name=tool_calls[i].tool_name,
                    status=ToolCallStatus.FAILED,
                    result=None,
                    error={
                        "message": f"Parallel execution error: {str(result)}",
                        "type": type(result).__name__
                    },
                    execution_time_ms=0.0
                )
                final_results.append(error_result)
            else:
                final_results.append(result)
        
        return final_results
    
    def get_tool_metrics(self, tool_name: str) -> ToolMetrics:
        """Get metrics for a specific tool"""
        return self._metrics[tool_name]
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all tools"""
        return {tool_name: metrics.to_dict() for tool_name, metrics in self._metrics.items()}
    
    def reset_metrics(self, tool_name: Optional[str] = None) -> None:
        """Reset metrics for a specific tool or all tools"""
        if tool_name:
            self._metrics[tool_name] = ToolMetrics()
        else:
            self._metrics.clear()


class ToolResult:
    """Wrapper for tool execution results"""
    
    def __init__(self, 
                 success: bool, 
                 data: Optional[Dict[str, Any]] = None, 
                 error: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.success = success
        self.data = data or {}
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def success_result(cls, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> 'ToolResult':
        """Create a successful tool result"""
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def error_result(cls, error: str, metadata: Optional[Dict[str, Any]] = None) -> 'ToolResult':
        """Create an error tool result"""
        return cls(success=False, error=error, metadata=metadata)


class BaseTool(ABC):
    """Abstract base class for all tools"""
    
    def __init__(self):
        self._definition: Optional[ToolDefinition] = None
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._metrics = ToolMetrics()
    
    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the tool definition including name, description, and parameters"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        """
        Execute the tool with given parameters and context
        
        Args:
            parameters: Validated parameters for the tool
            context: Execution context including session info
            
        Returns:
            ToolResult: Result of the tool execution
            
        Raises:
            ToolExecutionError: If tool execution fails
        """
        pass
    
    def get_metrics(self) -> ToolMetrics:
        """Get metrics for this tool instance"""
        return self._metrics
    
    async def validate_context(self, context: ToolExecutionContext) -> None:
        """Validate execution context (override in subclasses if needed)"""
        if not context.session_id:
            raise ToolValidationError(f"Session ID is required for tool '{self.definition.name}'", self.definition.name)
    
    async def pre_execute(self, parameters: Dict[str, Any], context: ToolExecutionContext) -> None:
        """Hook called before execute() (override in subclasses if needed)"""
        pass
    
    async def post_execute(self, result: ToolResult, parameters: Dict[str, Any], context: ToolExecutionContext) -> None:
        """Hook called after execute() (override in subclasses if needed)"""
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize parameters according to tool definition
        
        Args:
            parameters: Raw parameters to validate
            
        Returns:
            Dict[str, Any]: Validated and normalized parameters
            
        Raises:
            ToolValidationError: If validation fails
        """
        definition = self.definition
        validated = {}
        errors = {}
        
        # Check required parameters
        required_params = definition.get_required_parameters()
        for param_name in required_params:
            if param_name not in parameters:
                errors[param_name] = f"Required parameter '{param_name}' is missing"
        
        # Validate each provided parameter
        for param_name, param_value in parameters.items():
            param_def = definition.get_parameter_by_name(param_name)
            
            if param_def is None:
                errors[param_name] = f"Unknown parameter '{param_name}'"
                continue
            
            try:
                validated[param_name] = self._validate_parameter_value(param_def, param_value)
            except ValueError as e:
                errors[param_name] = str(e)
        
        # Add default values for missing optional parameters
        for param_def in definition.parameters:
            if not param_def.required and param_def.name not in validated and param_def.default is not None:
                validated[param_def.name] = param_def.default
        
        if errors:
            raise ToolValidationError(
                f"Parameter validation failed for tool '{definition.name}'",
                definition.name,
                errors
            )
        
        return validated
    
    def _validate_parameter_value(self, param_def: ToolParameter, value: Any) -> Any:
        """Validate a single parameter value against its definition"""
        from .schemas import ParameterType
        
        # Type validation
        if param_def.type == ParameterType.STRING:
            if not isinstance(value, str):
                raise ValueError(f"Expected string, got {type(value).__name__}")
            if param_def.min_length is not None and len(value) < param_def.min_length:
                raise ValueError(f"String too short (min: {param_def.min_length})")
            if param_def.max_length is not None and len(value) > param_def.max_length:
                raise ValueError(f"String too long (max: {param_def.max_length})")
            if param_def.pattern:
                import re
                if not re.match(param_def.pattern, value):
                    raise ValueError(f"String does not match pattern: {param_def.pattern}")
        
        elif param_def.type == ParameterType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"Expected integer, got {type(value).__name__}")
            if param_def.min_value is not None and value < param_def.min_value:
                raise ValueError(f"Value too small (min: {param_def.min_value})")
            if param_def.max_value is not None and value > param_def.max_value:
                raise ValueError(f"Value too large (max: {param_def.max_value})")
        
        elif param_def.type == ParameterType.NUMBER:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"Expected number, got {type(value).__name__}")
            if param_def.min_value is not None and value < param_def.min_value:
                raise ValueError(f"Value too small (min: {param_def.min_value})")
            if param_def.max_value is not None and value > param_def.max_value:
                raise ValueError(f"Value too large (max: {param_def.max_value})")
        
        elif param_def.type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValueError(f"Expected boolean, got {type(value).__name__}")
        
        elif param_def.type == ParameterType.ARRAY:
            if not isinstance(value, list):
                raise ValueError(f"Expected array, got {type(value).__name__}")
            if param_def.min_length is not None and len(value) < param_def.min_length:
                raise ValueError(f"Array too short (min: {param_def.min_length})")
            if param_def.max_length is not None and len(value) > param_def.max_length:
                raise ValueError(f"Array too long (max: {param_def.max_length})")
        
        elif param_def.type == ParameterType.OBJECT:
            if not isinstance(value, dict):
                raise ValueError(f"Expected object, got {type(value).__name__}")
        
        # Enum validation
        if param_def.enum and value not in param_def.enum:
            raise ValueError(f"Value must be one of {param_def.enum}")
        
        return value
    
    async def call(self, tool_call: ToolCall, context: ToolExecutionContext) -> ToolCallResult:
        """
        Execute the tool call and return a result
        
        Args:
            tool_call: The tool call to execute
            context: Execution context
            
        Returns:
            ToolCallResult: Complete result of the tool call
        """
        start_time = time.time()
        
        try:
            # Validate tool name matches
            if tool_call.tool_name != self.definition.name:
                raise ToolConfigurationError(
                    f"Tool name mismatch: expected '{self.definition.name}', got '{tool_call.tool_name}'",
                    self.definition.name
                )
            
            # Validate context
            await self.validate_context(context)
            
            # Validate parameters
            validated_params = self.validate_parameters(tool_call.parameters)
            
            # Pre-execute hook
            await self.pre_execute(validated_params, context)
            
            # Determine timeout
            timeout = tool_call.timeout_seconds or self.definition.timeout_seconds
            
            # Execute with timeout
            try:
                if timeout > 0:
                    result = await asyncio.wait_for(
                        self.execute(validated_params, context),
                        timeout=timeout
                    )
                else:
                    result = await self.execute(validated_params, context)
            except asyncio.TimeoutError:
                raise ToolTimeoutError(self.definition.name, timeout)
            
            # Post-execute hook
            await self.post_execute(result, validated_params, context)
            
            execution_time = (time.time() - start_time) * 1000
            
            # Create result
            if result.success:
                tool_result = ToolCallResult(
                    call_id=tool_call.id,
                    tool_name=self.definition.name,
                    status=ToolCallStatus.COMPLETED,
                    result=result.data,
                    error=None,
                    execution_time_ms=execution_time,
                    metadata=result.metadata
                )
            else:
                tool_result = ToolCallResult(
                    call_id=tool_call.id,
                    tool_name=self.definition.name,
                    status=ToolCallStatus.FAILED,
                    result=None,
                    error={
                        "message": result.error,
                        "type": "ToolExecutionError"
                    },
                    execution_time_ms=execution_time,
                    metadata=result.metadata
                )
            
            # Record metrics
            self._metrics.record_execution(tool_result)
            return tool_result
        
        except ToolError as e:
            execution_time = (time.time() - start_time) * 1000
            tool_result = ToolCallResult(
                call_id=tool_call.id,
                tool_name=self.definition.name,
                status=ToolCallStatus.FAILED if not isinstance(e, ToolTimeoutError) else ToolCallStatus.TIMEOUT,
                result=None,
                error=e.to_dict(),
                execution_time_ms=execution_time,
                metadata={}
            )
            self._metrics.record_execution(tool_result)
            return tool_result
        
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._logger.error(f"Unexpected error in tool '{self.definition.name}': {e}", exc_info=True)
            
            tool_result = ToolCallResult(
                call_id=tool_call.id,
                tool_name=self.definition.name,
                status=ToolCallStatus.FAILED,
                result=None,
                error={
                    "message": f"Unexpected error: {str(e)}",
                    "type": type(e).__name__
                },
                execution_time_ms=execution_time,
                metadata={}
            )
            self._metrics.record_execution(tool_result)
            return tool_result
    
    def get_openrouter_schema(self) -> Dict[str, Any]:
        """Get OpenRouter-compatible tool schema"""
        return self.definition.to_openrouter_schema()
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.definition.name}')"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.definition.name}', version='{self.definition.version}')"


# Helper functions for common tool patterns
def create_simple_tool(name: str, 
                      description: str, 
                      execute_func: Callable[[Dict[str, Any], ToolExecutionContext], Awaitable[ToolResult]],
                      parameters: Optional[List[ToolParameter]] = None,
                      version: str = "1.0.0",
                      timeout: float = 30.0) -> Type[BaseTool]:
    """Create a simple tool from a function"""
    
    class SimpleTool(BaseTool):
        def __init__(self):
            super().__init__()
            self._definition = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters or [],
                version=version,
                timeout_seconds=timeout
            )
        
        @property
        def definition(self) -> ToolDefinition:
            if self._definition is None:
                raise RuntimeError("Tool definition not initialized")
            return self._definition
        
        async def execute(self, parameters: Dict[str, Any], context: ToolExecutionContext) -> ToolResult:
            return await execute_func(parameters, context)
    
    return SimpleTool


async def create_error_middleware(allowed_error_types: List[str]) -> Callable[[ToolCall, ToolExecutionContext], Awaitable[Optional[ToolCall]]]:
    """Create middleware that filters allowed error types"""
    async def middleware(tool_call: ToolCall, context: ToolExecutionContext) -> Optional[ToolCall]:
        # This is just an example middleware - could be enhanced with actual filtering logic
        return tool_call
    return middleware


async def create_logging_processor() -> Callable[[ToolCallResult], Awaitable[ToolCallResult]]:
    """Create a result processor that logs tool execution results"""
    async def processor(result: ToolCallResult) -> ToolCallResult:
        logger.info(f"Tool '{result.tool_name}' executed with status: {result.status}, time: {result.execution_time_ms:.2f}ms")
        return result
    return processor


# Global tool executor instance
_global_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """Get or create the global tool executor instance"""
    global _global_executor
    if _global_executor is None:
        _global_executor = ToolExecutor()
    return _global_executor 