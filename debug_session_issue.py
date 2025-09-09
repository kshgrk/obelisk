#!/usr/bin/env python3
"""
Debug script for session 544f92a1-8b8c-4b3a-801a-92ecd8b4b86f
Tests various aspects of the chat system to identify empty response issues.
"""

import asyncio
import aiohttp
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging
import os
from pathlib import Path

# Configure logging to capture everything
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_session.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
SESSION_ID = "544f92a1-8b8c-4b3a-801a-92ecd8b4b86f"
BASE_URL = "http://localhost:8001"
API_BASE = BASE_URL  # No /api/v1 prefix based on server response

class SessionDebugger:
    """Comprehensive session debugging tool"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "session_id": SESSION_ID,
            "tests": {}
        }
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def log_test(self, test_name: str, result: Dict[str, Any]):
        """Log test results"""
        self.results["tests"][test_name] = {
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        logger.info(f"=== {test_name.upper()} ===")
        logger.info(json.dumps(result, indent=2))
        logger.info("=" * 50)
    
    async def check_server_health(self) -> Dict[str, Any]:
        """Test server connectivity and health"""
        try:
            if not self.session:
                return {"status": "session_not_initialized", "error": "HTTP session not initialized"}
            async with self.session.get(f"{API_BASE}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": "healthy",
                        "server_response": data,
                        "active_streams": data.get("active_streams", 0)
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "http_status": response.status,
                        "error": await response.text()
                    }
        except Exception as e:
            return {
                "status": "connection_failed",
                "error": str(e)
            }
    
    async def get_session_info(self) -> Dict[str, Any]:
        """Get comprehensive session information"""
        try:
            if not self.session:
                return {"status": "session_not_initialized", "error": "HTTP session not initialized"}
            async with self.session.get(f"{API_BASE}/sessions/{SESSION_ID}") as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": "found",
                        "session_data": data,
                        "conversation_history_length": len(data.get("conversation_history", [])),
                        "current_config": data.get("current_config", {}),
                        "statistics": data.get("statistics", {})
                    }
                elif response.status == 404:
                    return {
                        "status": "not_found",
                        "error": "Session does not exist"
                    }
                else:
                    return {
                        "status": "error",
                        "http_status": response.status,
                        "error": await response.text()
                    }
        except Exception as e:
            return {
                "status": "exception",
                "error": str(e)
            }
    
    async def get_session_tool_state(self) -> Dict[str, Any]:
        """Get session tool state from the API"""
        try:
            async with self.session.get(f"{API_BASE}/chat/tools/session/{SESSION_ID}/state") as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": "success",
                        "tool_state": data
                    }
                else:
                    return {
                        "status": "error",
                        "http_status": response.status,
                        "error": await response.text()
                    }
        except Exception as e:
            return {
                "status": "exception",
                "error": str(e)
            }
    
    async def test_model_switch(self, new_model: str) -> Dict[str, Any]:
        """Test model switching functionality"""
        try:
            payload = {
                "session_id": SESSION_ID,
                "new_model": new_model
            }
            
            async with self.session.post(
                f"{API_BASE}/chat/tools/switch-model",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": "success",
                        "switch_result": data
                    }
                else:
                    return {
                        "status": "error",
                        "http_status": response.status,
                        "error": await response.text()
                    }
        except Exception as e:
            return {
                "status": "exception",
                "error": str(e)
            }
    
    async def send_test_message(
        self, 
        message: str, 
        model_id: Optional[str] = None,
        stream: bool = True,
        config_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send a test message and capture the full response"""
        
        logger.info(f"Sending test message: '{message}' with model: {model_id}")
        
        payload = {
            "session_id": SESSION_ID,
            "message": message,
            "stream": stream
        }
        
        if model_id:
            payload["model_id"] = model_id
        
        if config_override:
            payload["config_override"] = config_override
        
        start_time = time.time()
        
        try:
            if stream:
                return await self._handle_streaming_response(payload, start_time)
            else:
                return await self._handle_non_streaming_response(payload, start_time)
                
        except Exception as e:
            return {
                "status": "exception",
                "error": str(e),
                "payload_sent": payload,
                "duration_ms": (time.time() - start_time) * 1000
            }
    
    async def _handle_streaming_response(self, payload: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """Handle streaming response"""
        chunks = []
        events = []
        content_received = ""
        
        try:
            async with self.session.post(
                f"{API_BASE}/chat",
                json=payload,
                headers={"Accept": "text/event-stream"}
            ) as response:
                
                logger.info(f"Streaming response status: {response.status}")
                
                if response.status != 200:
                    return {
                        "status": "http_error",
                        "http_status": response.status,
                        "error": await response.text(),
                        "duration_ms": (time.time() - start_time) * 1000
                    }
                
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            event_data = json.loads(data_str)
                            events.append(event_data)
                            
                            # Extract content from different event types
                            if event_data.get("event") == "RunResponse":
                                chunk_content = event_data.get("content", "")
                                content_received += chunk_content
                                chunks.append(chunk_content)
                            
                            elif event_data.get("event") == "RunCompleted":
                                final_content = event_data.get("content", "")
                                if final_content and not content_received:
                                    content_received = final_content
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse event data: {data_str}")
                            continue
                
                return {
                    "status": "success",
                    "streaming": True,
                    "content_received": content_received,
                    "total_chunks": len(chunks),
                    "total_events": len(events),
                    "events": events,
                    "first_chunk_time_ms": None,  # Could calculate if needed
                    "duration_ms": (time.time() - start_time) * 1000,
                    "payload_sent": payload,
                    "is_empty_response": len(content_received.strip()) == 0
                }
                
        except Exception as e:
            return {
                "status": "streaming_exception",
                "error": str(e),
                "content_received": content_received,
                "events_received": len(events),
                "duration_ms": (time.time() - start_time) * 1000
            }
    
    async def _handle_non_streaming_response(self, payload: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """Handle non-streaming response"""
        try:
            async with self.session.post(f"{API_BASE}/chat", json=payload) as response:
                
                logger.info(f"Non-streaming response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    content = data.get("response", "")
                    
                    return {
                        "status": "success",
                        "streaming": False,
                        "content_received": content,
                        "response_data": data,
                        "duration_ms": (time.time() - start_time) * 1000,
                        "payload_sent": payload,
                        "is_empty_response": len(content.strip()) == 0
                    }
                else:
                    return {
                        "status": "http_error",
                        "http_status": response.status,
                        "error": await response.text(),
                        "duration_ms": (time.time() - start_time) * 1000
                    }
                    
        except Exception as e:
            return {
                "status": "non_streaming_exception",
                "error": str(e),
                "duration_ms": (time.time() - start_time) * 1000
            }
    
    async def run_comprehensive_debug(self):
        """Run all debugging tests"""
        
        logger.info(f"Starting comprehensive debug for session: {SESSION_ID}")
        
        # Test 1: Server Health Check
        health_result = await self.check_server_health()
        await self.log_test("server_health", health_result)
        
        if health_result["status"] != "healthy":
            logger.error("Server is not healthy! Stopping debug session.")
            return
        
        # Test 2: Session Information
        session_info = await self.get_session_info()
        await self.log_test("session_info", session_info)
        
        if session_info["status"] != "found":
            logger.error("Session not found! Stopping debug session.")
            return
        
        # Test 3: Session Tool State
        tool_state = await self.get_session_tool_state()
        await self.log_test("session_tool_state", tool_state)
        
        # Test 4: Simple test message (current model)
        simple_test = await self.send_test_message(
            "Hello, this is a test message to check if you're responding correctly.",
            stream=True
        )
        await self.log_test("simple_message_current_model", simple_test)
        
        # Test 5: Non-streaming version of same message
        simple_test_non_stream = await self.send_test_message(
            "Hello, this is a test message to check if you're responding correctly.",
            stream=False
        )
        await self.log_test("simple_message_non_streaming", simple_test_non_stream)
        
        # Test 6: Test with explicit model (Mistral Small)
        mistral_test = await self.send_test_message(
            "Please respond with exactly 'Model test successful'",
            model_id="mistralai/mistral-small-3.2-24b-instruct:free",
            stream=True
        )
        await self.log_test("explicit_model_mistral", mistral_test)
        
        # Test 7: Test model switching
        switch_result = await self.test_model_switch("anthropic/claude-3-5-haiku:beta")
        await self.log_test("model_switch_claude", switch_result)
        
        # Test 8: Message after model switch
        after_switch_test = await self.send_test_message(
            "Has the model been switched? Please confirm which model you are.",
            stream=True
        )
        await self.log_test("message_after_model_switch", after_switch_test)
        
        # Test 9: Check tool state after switch
        tool_state_after_switch = await self.get_session_tool_state()
        await self.log_test("tool_state_after_switch", tool_state_after_switch)
        
        # Test 10: Multiple rapid messages to see if pattern emerges
        rapid_tests = []
        for i in range(3):
            rapid_result = await self.send_test_message(
                f"Rapid test message #{i+1}. Please respond with 'Rapid response {i+1}'",
                stream=True
            )
            rapid_tests.append(rapid_result)
            await asyncio.sleep(1)  # Small delay between messages
        
        await self.log_test("rapid_message_tests", {"tests": rapid_tests, "count": len(rapid_tests)})
        
        # Test 11: Tool calling test
        tool_test = await self.send_test_message(
            "What's the weather like? Please use the weather tool if available.",
            stream=True
        )
        await self.log_test("tool_calling_test", tool_test)
        
        # Test 12: Switch back to original model and test
        original_switch = await self.test_model_switch("mistralai/mistral-small-3.2-24b-instruct:free")
        await self.log_test("switch_back_to_original", original_switch)
        
        original_model_test = await self.send_test_message(
            "Back to original model. Please confirm this message is working.",
            stream=True
        )
        await self.log_test("back_to_original_model_test", original_model_test)
        
        # Final summary
        await self._generate_summary()
    
    async def _generate_summary(self):
        """Generate a summary of all test results"""
        summary = {
            "total_tests": len(self.results["tests"]),
            "empty_responses": [],
            "successful_responses": [],
            "errors": [],
            "model_switches": [],
            "recommendations": []
        }
        
        for test_name, test_data in self.results["tests"].items():
            result = test_data["result"]
            
            if "is_empty_response" in result:
                if result["is_empty_response"]:
                    summary["empty_responses"].append(test_name)
                else:
                    summary["successful_responses"].append(test_name)
            
            if result.get("status") == "error" or result.get("status") == "exception":
                summary["errors"].append({
                    "test": test_name,
                    "error": result.get("error", "Unknown error")
                })
            
            if "switch_result" in result:
                summary["model_switches"].append({
                    "test": test_name,
                    "success": result.get("status") == "success"
                })
        
        # Generate recommendations
        if summary["empty_responses"]:
            summary["recommendations"].append(
                f"Empty responses detected in {len(summary['empty_responses'])} tests. "
                "Check OpenRouter API connectivity and model availability."
            )
        
        if summary["errors"]:
            summary["recommendations"].append(
                f"{len(summary['errors'])} errors detected. Check logs for details."
            )
        
        if not summary["successful_responses"]:
            summary["recommendations"].append(
                "No successful responses! This indicates a systemic issue."
            )
        
        await self.log_test("debug_summary", summary)
        
        # Save full results to file
        with open(f"debug_results_{SESSION_ID}_{int(time.time())}.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        logger.info("=" * 60)
        logger.info("DEBUG COMPLETE - Check debug_results_*.json for full details")
        logger.info("=" * 60)


async def main():
    """Main debugging function"""
    print(f"🔍 Starting debug session for {SESSION_ID}")
    print(f"📊 Logs will be saved to debug_session.log")
    print(f"📄 Results will be saved to debug_results_*.json")
    print("=" * 60)
    
    async with SessionDebugger() as debugger:
        await debugger.run_comprehensive_debug()


if __name__ == "__main__":
    asyncio.run(main()) 