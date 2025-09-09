#!/usr/bin/env python3
"""
Comprehensive test script for session 544f92a1-8b8c-4b3a-801a-92ecd8b4b86f
Tests different free models with various types of questions to identify patterns.
"""

import asyncio
import aiohttp
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('model_test_session.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
SESSION_ID = "544f92a1-8b8c-4b3a-801a-92ecd8b4b86f"
BASE_URL = "http://localhost:8001"

# Free models to test
FREE_MODELS = [
    "openrouter/cypher-alpha:free",
    "deepseek/deepseek-chat-v3-0324:free", 
    "mistralai/mistral-small-3.2-24b-instruct:free",
    "meta-llama/llama-4-maverick:free"
]

# Different types of test questions
TEST_QUESTIONS = [
    {
        "type": "simple_greeting",
        "message": "Hello! Can you tell me what model you are?",
        "description": "Basic greeting and model identification"
    },
    {
        "type": "math_question", 
        "message": "What is 15 + 27? Please show your calculation.",
        "description": "Simple math to test basic reasoning"
    },
    {
        "type": "creative_writing",
        "message": "Write a short 2-sentence story about a robot discovering music for the first time.",
        "description": "Creative writing task"
    },
    {
        "type": "tool_request",
        "message": "Can you use the calculator tool to compute 123 * 456?",
        "description": "Explicit tool calling request"
    },
    {
        "type": "weather_request",
        "message": "What's the weather like in New York? Use the weather tool if available.",
        "description": "Weather tool request"
    },
    {
        "type": "code_generation",
        "message": "Write a simple Python function to reverse a string.",
        "description": "Code generation task"
    },
    {
        "type": "reasoning",
        "message": "If a train leaves New York at 3 PM traveling at 80 mph, and another leaves Boston at 4 PM traveling at 70 mph, when will they meet? (Distance between cities is 200 miles)",
        "description": "Multi-step reasoning problem"
    },
    {
        "type": "summarization",
        "message": "Summarize this text in one sentence: 'Artificial intelligence has transformed many industries. From healthcare to finance, AI systems are helping humans make better decisions. However, challenges remain in ensuring AI systems are fair and transparent.'",
        "description": "Text summarization task"
    }
]

class ModelTester:
    """Comprehensive model testing for the session"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "session_id": SESSION_ID,
            "models_tested": len(FREE_MODELS),
            "questions_per_model": len(TEST_QUESTIONS),
            "model_results": {}
        }
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def switch_model(self, model: str) -> Dict[str, Any]:
        """Switch the session to use a specific model"""
        if not self.session:
            return {"status": "error", "error": "No session available"}
            
        payload = {
            "session_id": SESSION_ID,
            "new_model": model
        }
        
        try:
            async with self.session.post(
                f"{BASE_URL}/chat/tools/switch-model",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Switched to model: {model}")
                    return {"status": "success", "data": data}
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to switch to {model}: {error_text}")
                    return {"status": "error", "error": error_text}
        except Exception as e:
            logger.error(f"❌ Exception switching to {model}: {e}")
            return {"status": "exception", "error": str(e)}
    
    async def get_session_state(self) -> Dict[str, Any]:
        """Get current session state"""
        if not self.session:
            return {"status": "error", "error": "No session available"}
            
        try:
            async with self.session.get(f"{BASE_URL}/chat/tools/session/{SESSION_ID}/state") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"status": "error", "error": await response.text()}
        except Exception as e:
            return {"status": "exception", "error": str(e)}
    
    async def send_message(
        self, 
        message: str, 
        stream: bool = True,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Send a message to the session"""
        if not self.session:
            return {"status": "error", "error": "No session available"}
            
        payload = {
            "session_id": SESSION_ID,
            "message": message,
            "stream": stream
        }
        
        start_time = time.time()
        
        try:
            if stream:
                return await self._handle_streaming_message(payload, start_time, timeout)
            else:
                return await self._handle_non_streaming_message(payload, start_time, timeout)
        except Exception as e:
            return {
                "status": "exception",
                "error": str(e),
                "duration_ms": (time.time() - start_time) * 1000
            }
    
    async def _handle_streaming_message(self, payload: Dict[str, Any], start_time: float, timeout: int) -> Dict[str, Any]:
        """Handle streaming message response"""
        content_received = ""
        events = []
        chunks = []
        
        try:
            async with self.session.post(
                f"{BASE_URL}/chat",
                json=payload,
                headers={"Accept": "text/event-stream"},
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                
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
                            
                            if event_data.get("event") == "RunResponse":
                                chunk_content = event_data.get("content", "")
                                content_received += chunk_content
                                chunks.append(chunk_content)
                            
                            elif event_data.get("event") == "RunCompleted":
                                final_content = event_data.get("content", "")
                                if final_content and not content_received:
                                    content_received = final_content
                                    
                        except json.JSONDecodeError:
                            continue
                
                return {
                    "status": "success",
                    "streaming": True,
                    "content_received": content_received,
                    "total_chunks": len(chunks),
                    "total_events": len(events),
                    "duration_ms": (time.time() - start_time) * 1000,
                    "is_empty_response": len(content_received.strip()) == 0,
                    "events": events[-3:] if len(events) > 3 else events  # Keep last 3 events for analysis
                }
                
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": f"Request timed out after {timeout}s",
                "content_received": content_received,
                "events_received": len(events),
                "duration_ms": (time.time() - start_time) * 1000
            }
    
    async def _handle_non_streaming_message(self, payload: Dict[str, Any], start_time: float, timeout: int) -> Dict[str, Any]:
        """Handle non-streaming message response"""
        try:
            async with self.session.post(
                f"{BASE_URL}/chat", 
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    content = data.get("response", "")
                    
                    return {
                        "status": "success",
                        "streaming": False,
                        "content_received": content,
                        "response_data": data,
                        "duration_ms": (time.time() - start_time) * 1000,
                        "is_empty_response": len(content.strip()) == 0
                    }
                else:
                    return {
                        "status": "http_error",
                        "http_status": response.status,
                        "error": await response.text(),
                        "duration_ms": (time.time() - start_time) * 1000
                    }
                    
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": f"Request timed out after {timeout}s",
                "duration_ms": (time.time() - start_time) * 1000
            }
    
    async def test_model_comprehensive(self, model: str) -> Dict[str, Any]:
        """Run comprehensive tests on a specific model"""
        
        logger.info(f"\n🤖 Starting comprehensive test for model: {model}")
        logger.info("=" * 70)
        
        model_results = {
            "model": model,
            "switch_result": {},
            "session_state": {},
            "question_results": {},
            "summary": {
                "total_questions": len(TEST_QUESTIONS),
                "successful_responses": 0,
                "empty_responses": 0,
                "errors": 0,
                "streaming_issues": 0,
                "average_response_time": 0
            }
        }
        
        # Step 1: Switch to the model
        switch_result = await self.switch_model(model)
        model_results["switch_result"] = switch_result
        
        if switch_result["status"] != "success":
            logger.error(f"❌ Failed to switch to {model}, skipping tests")
            return model_results
        
        # Small delay after model switch
        await asyncio.sleep(2)
        
        # Step 2: Get session state after switch
        session_state = await self.get_session_state()
        model_results["session_state"] = session_state
        
        # Step 3: Test each question type
        response_times = []
        
        for i, question in enumerate(TEST_QUESTIONS):
            logger.info(f"\n📝 Question {i+1}/{len(TEST_QUESTIONS)}: {question['type']}")
            logger.info(f"Message: {question['message'][:50]}...")
            
            # Test streaming first
            streaming_result = await self.send_message(question["message"], stream=True)
            
            # Also test non-streaming for comparison
            await asyncio.sleep(1)  # Small delay between requests
            non_streaming_result = await self.send_message(question["message"], stream=False)
            
            question_results = {
                "question_type": question["type"],
                "question": question["message"],
                "description": question["description"],
                "streaming_result": streaming_result,
                "non_streaming_result": non_streaming_result,
                "timestamp": datetime.now().isoformat()
            }
            
            model_results["question_results"][question["type"]] = question_results
            
            # Update summary statistics
            if streaming_result.get("status") == "success":
                if streaming_result.get("is_empty_response"):
                    model_results["summary"]["empty_responses"] += 1
                    if streaming_result.get("streaming"):
                        model_results["summary"]["streaming_issues"] += 1
                    logger.warning(f"⚠️  Empty response for {question['type']}")
                else:
                    model_results["summary"]["successful_responses"] += 1
                    logger.info(f"✅ Response received: {len(streaming_result.get('content_received', ''))} chars")
                
                response_times.append(streaming_result.get("duration_ms", 0))
            else:
                model_results["summary"]["errors"] += 1
                logger.error(f"❌ Error for {question['type']}: {streaming_result.get('error', 'Unknown')}")
            
            # Small delay between questions
            await asyncio.sleep(1)
        
        # Calculate average response time
        if response_times:
            model_results["summary"]["average_response_time"] = sum(response_times) / len(response_times)
        
        # Log model summary
        summary = model_results["summary"]
        logger.info(f"\n📊 Model {model} Summary:")
        logger.info(f"  ✅ Successful: {summary['successful_responses']}/{summary['total_questions']}")
        logger.info(f"  ⚠️  Empty: {summary['empty_responses']}/{summary['total_questions']}")
        logger.info(f"  ❌ Errors: {summary['errors']}/{summary['total_questions']}")
        logger.info(f"  🌊 Streaming issues: {summary['streaming_issues']}")
        logger.info(f"  ⏱️  Avg response time: {summary['average_response_time']:.1f}ms")
        
        return model_results
    
    async def run_comprehensive_test(self):
        """Run comprehensive tests across all models"""
        
        logger.info(f"🚀 Starting comprehensive model testing for session: {SESSION_ID}")
        logger.info(f"🧪 Testing {len(FREE_MODELS)} models with {len(TEST_QUESTIONS)} questions each")
        logger.info("=" * 70)
        
        # Test each model
        for i, model in enumerate(FREE_MODELS):
            logger.info(f"\n📊 Progress: Model {i+1}/{len(FREE_MODELS)}")
            
            try:
                model_results = await self.test_model_comprehensive(model)
                self.results["model_results"][model] = model_results
                
                # Longer delay between models to avoid rate limiting
                if i < len(FREE_MODELS) - 1:
                    logger.info("⏳ Waiting before next model...")
                    await asyncio.sleep(5)
                    
            except Exception as e:
                logger.error(f"❌ Failed to test model {model}: {e}")
                self.results["model_results"][model] = {
                    "model": model,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        # Generate overall summary
        await self._generate_overall_summary()
    
    async def _generate_overall_summary(self):
        """Generate overall test summary"""
        
        overall_summary = {
            "total_models_tested": len(FREE_MODELS),
            "total_questions_per_model": len(TEST_QUESTIONS),
            "model_performance": {},
            "problematic_models": [],
            "best_performing_models": [],
            "streaming_issues_by_model": {},
            "recommendations": []
        }
        
        for model, results in self.results["model_results"].items():
            if "summary" in results:
                summary = results["summary"]
                success_rate = (summary["successful_responses"] / summary["total_questions"]) * 100
                empty_rate = (summary["empty_responses"] / summary["total_questions"]) * 100
                
                overall_summary["model_performance"][model] = {
                    "success_rate": success_rate,
                    "empty_response_rate": empty_rate,
                    "average_response_time": summary["average_response_time"],
                    "streaming_issues": summary["streaming_issues"]
                }
                
                # Identify problematic models
                if empty_rate > 20:  # More than 20% empty responses
                    overall_summary["problematic_models"].append({
                        "model": model,
                        "empty_rate": empty_rate,
                        "streaming_issues": summary["streaming_issues"]
                    })
                
                # Identify best performing models
                if success_rate > 80 and empty_rate < 10:
                    overall_summary["best_performing_models"].append({
                        "model": model,
                        "success_rate": success_rate
                    })
                
                # Track streaming issues
                if summary["streaming_issues"] > 0:
                    overall_summary["streaming_issues_by_model"][model] = summary["streaming_issues"]
        
        # Generate recommendations
        if overall_summary["problematic_models"]:
            overall_summary["recommendations"].append(
                "Consider avoiding problematic models or implementing fallback mechanisms"
            )
        
        if overall_summary["streaming_issues_by_model"]:
            overall_summary["recommendations"].append(
                "Implement model-specific streaming detection and fallback to non-streaming for affected models"
            )
        
        if overall_summary["best_performing_models"]:
            best_model = overall_summary["best_performing_models"][0]["model"]
            overall_summary["recommendations"].append(
                f"Consider using {best_model} as the default model for better reliability"
            )
        
        self.results["overall_summary"] = overall_summary
        
        # Log final summary
        logger.info("\n" + "=" * 70)
        logger.info("🎯 FINAL TEST SUMMARY")
        logger.info("=" * 70)
        
        for model, perf in overall_summary["model_performance"].items():
            logger.info(f"{model}:")
            logger.info(f"  Success: {perf['success_rate']:.1f}%")
            logger.info(f"  Empty: {perf['empty_response_rate']:.1f}%")
            logger.info(f"  Streaming issues: {perf['streaming_issues']}")
            logger.info(f"  Avg time: {perf['average_response_time']:.1f}ms")
        
        if overall_summary["recommendations"]:
            logger.info("\n💡 Recommendations:")
            for rec in overall_summary["recommendations"]:
                logger.info(f"  • {rec}")
        
        # Save detailed results
        filename = f"model_test_results_{SESSION_ID}_{int(time.time())}.json"
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"\n📄 Detailed results saved to: {filename}")
        logger.info("🏁 Testing complete!")


async def main():
    """Main testing function"""
    print(f"🔬 Starting comprehensive model testing for session: {SESSION_ID}")
    print(f"🧪 Testing models: {', '.join(FREE_MODELS)}")
    print(f"📝 Questions per model: {len(TEST_QUESTIONS)}")
    print("=" * 70)
    
    async with ModelTester() as tester:
        await tester.run_comprehensive_test()


if __name__ == "__main__":
    asyncio.run(main()) 