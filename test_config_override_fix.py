#!/usr/bin/env python3
"""
Test script to verify config override fix for immediate model switching
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8001"

async def test_config_override_fix():
    """Test that config override works immediately on first message"""
    
    print("🧪 Testing Config Override Fix")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        
        # Step 1: Create a new session
        print("1️⃣ Creating new session...")
        async with session.post(f"{BASE_URL}/sessions") as response:
            if response.status == 200:
                session_data = await response.json()
                session_id = session_data["id"]
                print(f"✅ Created session: {session_id}")
            else:
                print(f"❌ Failed to create session: {response.status}")
                return
        
        # Step 2: Send first message with config override (different model)
        print("\n2️⃣ Sending first message with config override...")
        
        # Use a model different from the default (deepseek)
        config_override = {
            "model": "openrouter/cypher-alpha:free"  # Different from default
        }
        
        payload = {
            "session_id": session_id,
            "message": "Hello! What model are you? Please tell me your exact model name.",
            "stream": False,
            "config_override": config_override
        }
        
        start_time = time.time()
        
        async with session.post(f"{BASE_URL}/chat", json=payload) as response:
            response_time = (time.time() - start_time) * 1000
            
            if response.status == 200:
                data = await response.json()
                response_text = data.get("response", "")
                
                print(f"✅ Response received in {response_time:.1f}ms")
                print(f"📝 Response: {response_text}")
                
                # Check if the response indicates correct model usage
                if "cypher" in response_text.lower() or "openrouter" in response_text.lower():
                    print("✅ SUCCESS: Model override worked! Response mentions the correct model.")
                elif "deepseek" in response_text.lower():
                    print("❌ FAILED: Response still shows DeepSeek (default model).")
                    print("   Config override was not applied properly.")
                else:
                    print("⚠️  UNCLEAR: Response doesn't clearly indicate which model was used.")
                    print("   Need to check backend logs to confirm.")
                
            else:
                error_text = await response.text()
                print(f"❌ Failed to send message: {response.status}")
                print(f"   Error: {error_text}")
                return
        
        # Step 3: Get session info to verify model was set
        print("\n3️⃣ Checking session state...")
        async with session.get(f"{BASE_URL}/sessions/{session_id}") as response:
            if response.status == 200:
                session_info = await response.json()
                session_config = session_info.get("session_data", {}).get("config", {})
                current_model = session_config.get("model", "unknown")
                print(f"📊 Session model: {current_model}")
                
                if current_model == "openrouter/cypher-alpha:free":
                    print("✅ SUCCESS: Session model matches config override!")
                else:
                    print(f"❌ FAILED: Session model is '{current_model}', expected 'openrouter/cypher-alpha:free'")
            else:
                print(f"❌ Failed to get session info: {response.status}")
        
        print("\n" + "=" * 50)
        print("🎯 Test Complete!")

async def test_frontend_proxy():
    """Test that the frontend proxy correctly forwards config_override"""
    
    print("\n🔗 Testing Frontend Proxy")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        
        # Create new session through frontend proxy
        print("1️⃣ Creating session through frontend proxy...")
        async with session.post("http://localhost:8000/api/sessions") as response:
            if response.status == 200:
                session_data = await response.json()
                session_id = session_data["id"]
                print(f"✅ Created session via frontend: {session_id}")
            else:
                print(f"❌ Failed to create session via frontend: {response.status}")
                return
        
        # Send message through frontend proxy with config override
        print("\n2️⃣ Sending message through frontend proxy with config override...")
        
        config_override = {
            "model": "meta-llama/llama-4-maverick:free"
        }
        
        payload = {
            "session_id": session_id,
            "message": "Hello! Can you tell me what model you are?",
            "stream": False,
            "config_override": config_override
        }
        
        start_time = time.time()
        
        async with session.post("http://localhost:8000/api/chat", json=payload) as response:
            response_time = (time.time() - start_time) * 1000
            
            if response.status == 200:
                data = await response.json()
                response_text = data.get("response", "")
                
                print(f"✅ Frontend proxy response in {response_time:.1f}ms")
                print(f"📝 Response: {response_text}")
                
                if "llama" in response_text.lower() or "maverick" in response_text.lower():
                    print("✅ SUCCESS: Frontend proxy correctly forwarded config override!")
                elif "deepseek" in response_text.lower():
                    print("❌ FAILED: Frontend proxy did not forward config override.")
                else:
                    print("⚠️  UNCLEAR: Need to check logs to verify model used.")
                
            else:
                error_text = await response.text()
                print(f"❌ Frontend proxy failed: {response.status}")
                print(f"   Error: {error_text}")

async def main():
    """Run all tests"""
    print(f"🚀 Config Override Fix Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Wait a moment for servers to be ready
    await asyncio.sleep(2)
    
    try:
        await test_config_override_fix()
        await test_frontend_proxy()
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 