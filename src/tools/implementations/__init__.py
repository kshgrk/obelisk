"""
Tool implementations package

This package contains concrete implementations of tools that inherit from BaseTool.
Tools in this package are automatically discovered and registered by the ToolRegistry.

Available Tools:
- CalculatorTool: Basic mathematical operations (add, subtract, multiply, divide, power, sqrt)
- WeatherTool: Mock weather information with realistic fake data
"""

# Import all tool implementations here for easier access
from .calculator import CalculatorTool
from .weather import WeatherTool

__all__ = [
    'CalculatorTool',
    'WeatherTool'
] 