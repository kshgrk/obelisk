"""
Calculator Tool Implementation

Provides basic mathematical operations including addition, subtraction,
multiplication, and division with proper error handling and validation.
"""

import math
from typing import Dict, Any
from decimal import Decimal, InvalidOperation

from ..base import BaseTool, ToolResult
from ..schemas import ToolDefinition, ToolParameter, ParameterType, ToolExecutionContext
from ..exceptions import ToolValidationError, ToolExecutionError


class CalculatorTool(BaseTool):
    """
    Calculator tool for basic mathematical operations
    
    Supports:
    - Addition (add)
    - Subtraction (subtract)  
    - Multiplication (multiply)
    - Division (divide)
    - Power (power)
    - Square root (sqrt)
    
    Returns JSON formatted results with operation details.
    """
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="calculator",
            description="Perform basic mathematical operations including addition, subtraction, multiplication, division, power, and square root",
            version="1.0.0",
            timeout_seconds=10.0,
            parameters=[
                ToolParameter(
                    name="operation",
                    type=ParameterType.STRING,
                    description="Mathematical operation to perform",
                    required=True,
                    enum=["add", "subtract", "multiply", "divide", "power", "sqrt"]
                ),
                ToolParameter(
                    name="a",
                    type=ParameterType.NUMBER,
                    description="First number (operand)",
                    required=True
                ),
                ToolParameter(
                    name="b", 
                    type=ParameterType.NUMBER,
                    description="Second number (operand). Not required for sqrt operation.",
                    required=False
                ),
                ToolParameter(
                    name="precision",
                    type=ParameterType.INTEGER,
                    description="Number of decimal places for the result",
                    required=False,
                    default=2,
                    min_value=0,
                    max_value=10
                )
            ]
        )
    
    async def validate_context(self, context: ToolExecutionContext) -> None:
        """Validate execution context for calculator operations"""
        await super().validate_context(context)
        
        # Calculator doesn't need special session validation
        # but we can log usage for analytics
        self._logger.debug(f"Calculator tool used in session {context.session_id}")
    
    async def pre_execute(self, parameters: Dict[str, Any], context: ToolExecutionContext) -> None:
        """Pre-execution validation for calculator operations"""
        operation = parameters.get("operation")
        a = parameters.get("a")
        b = parameters.get("b")
        
        # Validate that a is provided and is a number
        if a is None:
            raise ToolValidationError(
                "Parameter 'a' is required",
                self.definition.name,
                {"a": "Required parameter"}
            )
        
        # Validate operation-specific requirements
        if operation == "sqrt":
            if float(a) < 0:
                raise ToolValidationError(
                    "Square root of negative numbers is not supported",
                    self.definition.name,
                    {"a": "Must be non-negative for sqrt operation"}
                )
        elif operation == "divide":
            if b is None:
                raise ToolValidationError(
                    f"Parameter 'b' is required for {operation} operation",
                    self.definition.name,
                    {"b": f"Required for {operation} operation"}
                )
            if float(b) == 0:
                raise ToolValidationError(
                    "Division by zero is not allowed",
                    self.definition.name,
                    {"b": "Cannot be zero for division operation"}
                )
        elif operation in ["add", "subtract", "multiply", "power"]:
            if b is None:
                raise ToolValidationError(
                    f"Parameter 'b' is required for {operation} operation",
                    self.definition.name,
                    {"b": f"Required for {operation} operation"}
                )
        
        # Validate number ranges to prevent overflow
        max_value = 1e15
        if abs(float(a)) > max_value:
            raise ToolValidationError(
                "Numbers too large for calculation",
                self.definition.name,
                {"range": f"Numbers must be between -{max_value} and {max_value}"}
            )
        if b is not None and abs(float(b)) > max_value:
            raise ToolValidationError(
                "Numbers too large for calculation",
                self.definition.name,
                {"range": f"Numbers must be between -{max_value} and {max_value}"}
            )
    
    async def execute(self, parameters: Dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        """Execute the calculator operation"""
        try:
            operation = parameters["operation"]
            a = float(parameters["a"])
            b_param = parameters.get("b")
            b = float(b_param) if b_param is not None else None
            precision = parameters.get("precision", 2)
            
            # Perform the calculation
            result: float
            operation_symbol = ""
            
            if operation == "add" and b is not None:
                result = a + b
                operation_symbol = "+"
            elif operation == "subtract" and b is not None:
                result = a - b
                operation_symbol = "-"
            elif operation == "multiply" and b is not None:
                result = a * b
                operation_symbol = "*"
            elif operation == "divide" and b is not None:
                result = a / b
                operation_symbol = "/"
            elif operation == "power" and b is not None:
                result = a ** b
                operation_symbol = "**"
            elif operation == "sqrt":
                result = math.sqrt(a)
                operation_symbol = "√"
            else:
                # This should not happen due to pre_execute validation
                raise ToolExecutionError(f"Invalid operation or missing required parameter: {operation}", self.definition.name)
            
            # Round to specified precision
            result_rounded = round(result, precision)
            
            # Create formatted expression
            if operation == "sqrt":
                expression = f"√{a}"
            else:
                expression = f"{a} {operation_symbol} {b}"
            
            # Prepare result data
            result_data = {
                "operation": operation,
                "expression": expression,
                "operands": {"a": a, "b": b} if b is not None else {"a": a},
                "result": result_rounded,
                "raw_result": result,
                "precision": precision,
                "session_id": context.session_id,
                "calculation_metadata": {
                    "operation_type": operation,
                    "operand_count": 2 if b is not None else 1,
                    "result_type": "integer" if result_rounded == int(result_rounded) else "decimal"
                }
            }
            
            # Add additional context for specific operations
            if operation == "divide" and result_rounded == int(result_rounded):
                result_data["calculation_metadata"]["division_type"] = "exact"
            elif operation == "divide":
                result_data["calculation_metadata"]["division_type"] = "decimal"
            
            if operation == "power" and b == 2:
                result_data["calculation_metadata"]["special_operation"] = "square"
            elif operation == "power" and b == 3:
                result_data["calculation_metadata"]["special_operation"] = "cube"
            
            self._logger.info(f"Calculator operation completed: {expression} = {result_rounded}")
            
            return ToolResult.success_result(
                data=result_data,
                metadata={
                    "tool_version": self.definition.version,
                    "operation_count": 1,
                    "precision_used": precision
                }
            )
            
        except ZeroDivisionError:
            error_msg = "Division by zero is not allowed"
            self._logger.warning(f"Calculator error: {error_msg}")
            return ToolResult.error_result(
                error=error_msg,
                metadata={
                    "error_type": "division_by_zero",
                    "operation": parameters.get("operation"),
                    "operands": {"a": parameters.get("a"), "b": parameters.get("b")}
                }
            )
            
        except OverflowError:
            error_msg = "Calculation result is too large to represent"
            self._logger.warning(f"Calculator error: {error_msg}")
            return ToolResult.error_result(
                error=error_msg,
                metadata={
                    "error_type": "overflow",
                    "operation": parameters.get("operation"),
                    "operands": {"a": parameters.get("a"), "b": parameters.get("b")}
                }
            )
            
        except (ValueError, InvalidOperation) as e:
            error_msg = f"Invalid number format or calculation: {str(e)}"
            self._logger.warning(f"Calculator error: {error_msg}")
            return ToolResult.error_result(
                error=error_msg,
                metadata={
                    "error_type": "invalid_number",
                    "operation": parameters.get("operation"),
                    "original_error": str(e)
                }
            )
            
        except Exception as e:
            error_msg = f"Unexpected calculation error: {str(e)}"
            self._logger.error(f"Calculator unexpected error: {error_msg}", exc_info=True)
            return ToolResult.error_result(
                error=error_msg,
                metadata={
                    "error_type": "unexpected_error",
                    "operation": parameters.get("operation"),
                    "original_error": str(e)
                }
            )
    
    async def post_execute(self, result: ToolResult, parameters: Dict[str, Any], context: ToolExecutionContext) -> None:
        """Post-execution logging and cleanup"""
        if result.success:
            operation = parameters.get("operation")
            calc_result = result.data.get("result")
            self._logger.debug(f"Calculator {operation} completed successfully: result = {calc_result}")
        else:
            self._logger.warning(f"Calculator operation failed: {result.error}")


# Export the tool class for auto-discovery
__all__ = ["CalculatorTool"] 