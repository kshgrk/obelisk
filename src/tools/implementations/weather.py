"""
Weather Tool Implementation

Provides mock weather information for any location. Returns realistic-looking
fake weather data in JSON format for testing and demonstration purposes.
"""

import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List
from dataclasses import dataclass

from ..base import BaseTool, ToolResult
from ..schemas import ToolDefinition, ToolParameter, ParameterType, ToolExecutionContext
from ..exceptions import ToolValidationError, ToolExecutionError


@dataclass
class WeatherCondition:
    """Weather condition data structure"""
    condition: str
    description: str
    icon: str
    temp_modifier: float  # Multiplier for base temperature


class WeatherTool(BaseTool):
    """
    Mock weather tool that returns realistic fake weather data
    
    Provides:
    - Current weather conditions
    - Temperature in Celsius or Fahrenheit
    - Humidity, wind speed, and atmospheric pressure
    - Weather forecast (optional)
    - Weather warnings and alerts (randomly generated)
    
    Returns JSON formatted weather information for any location.
    """
    
    # Predefined weather conditions for realistic mock data
    WEATHER_CONDITIONS = [
        WeatherCondition("clear", "Clear sky", "☀️", 1.0),
        WeatherCondition("partly-cloudy", "Partly cloudy", "⛅", 0.95),
        WeatherCondition("cloudy", "Cloudy", "☁️", 0.9),
        WeatherCondition("overcast", "Overcast", "☁️", 0.85),
        WeatherCondition("light-rain", "Light rain", "🌧️", 0.8),
        WeatherCondition("rain", "Rain", "🌧️", 0.75),
        WeatherCondition("heavy-rain", "Heavy rain", "⛈️", 0.7),
        WeatherCondition("thunderstorm", "Thunderstorm", "⛈️", 0.65),
        WeatherCondition("snow", "Snow", "❄️", 0.4),
        WeatherCondition("fog", "Fog", "🌫️", 0.8),
        WeatherCondition("windy", "Windy", "💨", 0.9)
    ]
    
    CLIMATE_ZONES = {
        "tropical": {"base_temp": 28, "humidity": 80, "variation": 8},
        "temperate": {"base_temp": 18, "humidity": 60, "variation": 15},
        "continental": {"base_temp": 10, "humidity": 50, "variation": 25},
        "polar": {"base_temp": -10, "humidity": 70, "variation": 20},
        "desert": {"base_temp": 25, "humidity": 20, "variation": 20}
    }
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="weather",
            description="Get mock weather information for any location including current conditions, temperature, humidity, and optional forecast",
            version="1.0.0",
            timeout_seconds=5.0,
            parameters=[
                ToolParameter(
                    name="location",
                    type=ParameterType.STRING,
                    description="Location name (city, country, or coordinates)",
                    required=True,
                    min_length=2,
                    max_length=100
                ),
                ToolParameter(
                    name="units",
                    type=ParameterType.STRING,
                    description="Temperature units",
                    required=False,
                    default="celsius",
                    enum=["celsius", "fahrenheit", "kelvin"]
                ),
                ToolParameter(
                    name="include_forecast",
                    type=ParameterType.BOOLEAN,
                    description="Include 5-day weather forecast",
                    required=False,
                    default=False
                ),
                ToolParameter(
                    name="climate_zone",
                    type=ParameterType.STRING,
                    description="Climate zone for more realistic data",
                    required=False,
                    enum=["tropical", "temperate", "continental", "polar", "desert", "auto"],
                    default="auto"
                )
            ]
        )
    
    async def validate_context(self, context: ToolExecutionContext) -> None:
        """Validate execution context for weather operations"""
        await super().validate_context(context)
        
        # Log weather tool usage for analytics
        self._logger.debug(f"Weather tool used in session {context.session_id}")
    
    async def pre_execute(self, parameters: Dict[str, Any], context: ToolExecutionContext) -> None:
        """Pre-execution validation for weather requests"""
        location = parameters.get("location", "").strip()
        
        if not location:
            raise ToolValidationError(
                "Location cannot be empty",
                self.definition.name,
                {"location": "Must provide a valid location name"}
            )
        
        # Validate location format (basic validation)
        if len(location) < 2:
            raise ToolValidationError(
                "Location name too short",
                self.definition.name,
                {"location": "Location name must be at least 2 characters"}
            )
        
        if any(char in location for char in ['<', '>', '&', '"', "'"]):
            raise ToolValidationError(
                "Location contains invalid characters",
                self.definition.name,
                {"location": "Location cannot contain HTML/script characters"}
            )
        
        self._logger.debug(f"Weather request validated for location: {location}")
    
    def _determine_climate_zone(self, location: str) -> str:
        """Determine climate zone based on location (simplified mock logic)"""
        location_lower = location.lower()
        
        # Simple keyword-based climate detection for demo
        if any(keyword in location_lower for keyword in ['canada', 'russia', 'alaska', 'siberia', 'greenland']):
            return 'polar'
        elif any(keyword in location_lower for keyword in ['sahara', 'nevada', 'arizona', 'dubai', 'riyadh']):
            return 'desert'
        elif any(keyword in location_lower for keyword in ['thailand', 'brazil', 'india', 'philippines', 'tropical']):
            return 'tropical'
        elif any(keyword in location_lower for keyword in ['europe', 'china', 'japan', 'temperate']):
            return 'temperate'
        else:
            return 'continental'  # Default
    
    def _generate_deterministic_weather(self, location: str, climate_zone: str) -> Dict[str, Any]:
        """Generate deterministic weather data based on location hash"""
        # Use location hash for deterministic but pseudo-random data
        location_hash = hashlib.md5(location.encode()).hexdigest()
        seed_value = int(location_hash[:8], 16)
        random.seed(seed_value)
        
        # Get climate data
        climate = self.CLIMATE_ZONES[climate_zone]
        base_temp = climate["base_temp"]
        base_humidity = climate["humidity"]
        temp_variation = climate["variation"]
        
        # Generate deterministic weather
        condition = random.choice(self.WEATHER_CONDITIONS)
        
        # Temperature with seasonal and daily variation
        now = datetime.utcnow()
        seasonal_modifier = 0.8 if now.month in [12, 1, 2] else 1.2 if now.month in [6, 7, 8] else 1.0
        daily_variation = random.uniform(-temp_variation/2, temp_variation/2)
        
        temperature_c = base_temp * seasonal_modifier * condition.temp_modifier + daily_variation
        
        # Other weather parameters
        humidity = max(10, min(100, base_humidity + random.randint(-20, 20)))
        wind_speed = random.uniform(0, 25)
        pressure = random.uniform(980, 1030)
        visibility = random.uniform(5, 30)
        uv_index = max(0, min(11, random.uniform(0, 8)))
        
        return {
            "condition": condition,
            "temperature_c": round(temperature_c, 1),
            "humidity": humidity,
            "wind_speed": round(wind_speed, 1),
            "pressure": round(pressure, 1),
            "visibility": round(visibility, 1),
            "uv_index": round(uv_index, 1)
        }
    
    def _convert_temperature(self, temp_c: float, units: str) -> float:
        """Convert temperature to requested units"""
        if units == "fahrenheit":
            return round((temp_c * 9/5) + 32, 1)
        elif units == "kelvin":
            return round(temp_c + 273.15, 1)
        else:  # celsius
            return temp_c
    
    def _generate_forecast(self, location: str, climate_zone: str, units: str) -> List[Dict[str, Any]]:
        """Generate 5-day weather forecast"""
        forecast = []
        base_weather = self._generate_deterministic_weather(location, climate_zone)
        
        for day in range(1, 6):
            # Slight variations for each day
            daily_seed = hashlib.md5(f"{location}_{day}".encode()).hexdigest()
            random.seed(int(daily_seed[:8], 16))
            
            condition = random.choice(self.WEATHER_CONDITIONS)
            temp_variation = random.uniform(-5, 5)
            
            forecast_date = datetime.utcnow() + timedelta(days=day)
            temp_c = base_weather["temperature_c"] + temp_variation
            
            forecast.append({
                "date": forecast_date.strftime("%Y-%m-%d"),
                "day_name": forecast_date.strftime("%A"),
                "condition": condition.condition,
                "description": condition.description,
                "icon": condition.icon,
                "temperature": self._convert_temperature(temp_c, units),
                "humidity": max(20, min(90, base_weather["humidity"] + random.randint(-15, 15))),
                "wind_speed": round(max(0, base_weather["wind_speed"] + random.uniform(-5, 5)), 1)
            })
        
        return forecast
    
    def _generate_alerts(self, weather_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate weather alerts based on conditions"""
        alerts = []
        
        # Generate alerts based on weather conditions
        if weather_data["wind_speed"] > 20:
            alerts.append({
                "type": "wind",
                "severity": "moderate",
                "message": "High wind speeds expected. Secure outdoor objects."
            })
        
        if weather_data["condition"].condition in ["thunderstorm", "heavy-rain"]:
            alerts.append({
                "type": "severe_weather",
                "severity": "high", 
                "message": "Severe weather conditions. Avoid outdoor activities."
            })
        
        if weather_data["temperature_c"] > 35:
            alerts.append({
                "type": "heat",
                "severity": "moderate",
                "message": "High temperature warning. Stay hydrated and avoid prolonged sun exposure."
            })
        elif weather_data["temperature_c"] < -10:
            alerts.append({
                "type": "cold",
                "severity": "moderate", 
                "message": "Freezing temperatures. Dress warmly and check on vulnerable individuals."
            })
        
        if weather_data["uv_index"] > 7:
            alerts.append({
                "type": "uv",
                "severity": "moderate",
                "message": "High UV index. Use sunscreen and limit midday sun exposure."
            })
        
        return alerts
    
    async def execute(self, parameters: Dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        """Execute the weather information request"""
        try:
            location = parameters["location"].strip()
            units = parameters.get("units", "celsius")
            include_forecast = parameters.get("include_forecast", False)
            climate_zone = parameters.get("climate_zone", "auto")
            
            # Determine climate zone if auto
            if climate_zone == "auto":
                climate_zone = self._determine_climate_zone(location)
            
            # Generate base weather data
            weather_data = self._generate_deterministic_weather(location, climate_zone)
            condition = weather_data["condition"]
            
            # Convert temperature to requested units
            temperature = self._convert_temperature(weather_data["temperature_c"], units)
            
            # Build response data
            result_data = {
                "location": location,
                "climate_zone": climate_zone,
                "timestamp": datetime.utcnow().isoformat(),
                "units": {
                    "temperature": units,
                    "wind_speed": "km/h",
                    "pressure": "hPa",
                    "visibility": "km"
                },
                "current_weather": {
                    "condition": condition.condition,
                    "description": condition.description,
                    "icon": condition.icon,
                    "temperature": temperature,
                    "humidity": weather_data["humidity"],
                    "wind_speed": weather_data["wind_speed"],
                    "atmospheric_pressure": weather_data["pressure"],
                    "visibility": weather_data["visibility"],
                    "uv_index": weather_data["uv_index"]
                },
                "data_source": "mock_weather_service",
                "session_id": context.session_id
            }
            
            # Add forecast if requested
            if include_forecast:
                result_data["forecast"] = self._generate_forecast(location, climate_zone, units)
            
            # Add weather alerts
            alerts = self._generate_alerts(weather_data)
            if alerts:
                result_data["alerts"] = alerts
            
            # Add metadata about data generation
            result_data["metadata"] = {
                "is_mock_data": True,
                "generated_at": datetime.utcnow().isoformat(),
                "location_hash": hashlib.md5(location.encode()).hexdigest()[:8],
                "climate_zone_detected": climate_zone,
                "forecast_included": include_forecast,
                "alert_count": len(alerts)
            }
            
            self._logger.info(f"Weather data generated for {location} ({climate_zone} climate)")
            
            return ToolResult.success_result(
                data=result_data,
                metadata={
                    "tool_version": self.definition.version,
                    "location": location,
                    "units": units,
                    "forecast_included": include_forecast
                }
            )
            
        except KeyError as e:
            error_msg = f"Missing required parameter: {str(e)}"
            self._logger.warning(f"Weather tool parameter error: {error_msg}")
            return ToolResult.error_result(
                error=error_msg,
                metadata={
                    "error_type": "missing_parameter",
                    "location": parameters.get("location", "unknown"),
                    "original_error": str(e)
                }
            )
            
        except ValueError as e:
            error_msg = f"Invalid parameter value: {str(e)}"
            self._logger.warning(f"Weather tool value error: {error_msg}")
            return ToolResult.error_result(
                error=error_msg,
                metadata={
                    "error_type": "invalid_value",
                    "location": parameters.get("location", "unknown"),
                    "original_error": str(e)
                }
            )
            
        except Exception as e:
            error_msg = f"Unexpected weather service error: {str(e)}"
            self._logger.error(f"Weather tool unexpected error: {error_msg}", exc_info=True)
            return ToolResult.error_result(
                error=error_msg,
                metadata={
                    "error_type": "unexpected_error",
                    "location": parameters.get("location", "unknown"),
                    "original_error": str(e)
                }
            )
    
    async def post_execute(self, result: ToolResult, parameters: Dict[str, Any], context: ToolExecutionContext) -> None:
        """Post-execution logging and cleanup"""
        if result.success:
            location = parameters.get("location", "unknown")
            weather_condition = result.data.get("current_weather", {}).get("condition", "unknown")
            self._logger.debug(f"Weather data successfully generated for {location}: {weather_condition}")
        else:
            self._logger.warning(f"Weather request failed: {result.error}")


# Export the tool class for auto-discovery
__all__ = ["WeatherTool"] 