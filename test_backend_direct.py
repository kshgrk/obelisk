#!/usr/bin/env python3
"""
Direct backend test to verify config override processing
"""

import asyncio
import aiohttp
import json

async def test_backend_config_override():
    """Test backend directly to see config override processing"""
    
    print("🔬 Testing Backend Config Override Processing")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        
        # Step 1: Create session
        print("1️⃣ Creating new session...")
        async with session.post("http://localhost:8001/sessions") as response:
            if response.status == 200:
                session_data = await response.json()
                session_id = session_data["id"]
                print(f"✅ Created session: {session_id}")
            else:
                print(f"❌ Failed to create session: {response.status}")
                return
        
        # Step 2: Send message with config override DIRECTLY to backend
        print("\n2️⃣ Sending message with config override to backend...")
        
        payload = {
            "session_id": session_id,
            "message": "What model are you? Tell me your exact model name.",
            "stream": False,
            "config_override": {
                "model": "openrouter/cypher-alpha:free"
            }
        }
        
        print(f"📤 Payload: {json.dumps(payload, indent=2)}")
        
        async with session.post("http://localhost:8001/chat", json=payload) as response:
            print(f"📥 Response status: {response.status}")
            
            if response.status == 200:
                data = await response.json()
                print(f"📝 Response: {data.get('response', 'No response field')}")
                
                # Check if model switch worked
                if 'cypher' in data.get('response', '').lower():
                    print("✅ SUCCESS: Response mentions Cypher model")
                elif 'deepseek' in data.get('response', '').lower():
                    print("❌ FAILED: Still using DeepSeek (default)")
                else:
                    print("⚠️  UNCLEAR: Response doesn't clearly indicate model")
                    
            else:
                error_text = await response.text()
                print(f"❌ Backend error: {error_text}")
                return
        
        # Step 3: Check session state
        print("\n3️⃣ Checking session state...")
        async with session.get(f"http://localhost:8001/sessions/{session_id}") as response:
            if response.status == 200:
                session_info = await response.json()
                current_model = session_info.get("session_data", {}).get("config", {}).get("model")
                print(f"📊 Session model in database: {current_model}")
                
                if current_model == "openrouter/cypher-alpha:free":
                    print("✅ SUCCESS: Session model updated correctly")
                else:
                    print(f"❌ FAILED: Expected 'openrouter/cypher-alpha:free', got '{current_model}'")
            else:
                print(f"❌ Failed to get session state: {response.status}")
        
        # Step 4: Test tool state endpoint to see model switch results
        print("\n4️⃣ Checking tool state endpoint...")
        async with session.get(f"http://localhost:8001/chat/tools/session/{session_id}/state") as response:
            if response.status == 200:
                tool_state = await response.json()
                if tool_state.get("success"):
                    current_model_from_tools = tool_state.get("current_model")
                    print(f"🔧 Model from tool registry: {current_model_from_tools}")
                    
                    if current_model_from_tools == "openrouter/cypher-alpha:free":
                        print("✅ SUCCESS: Tool registry shows correct model")
                    else:
                        print(f"❌ FAILED: Tool registry shows '{current_model_from_tools}'")
                else:
                    print(f"❌ Tool state error: {tool_state}")
            else:
                print(f"❌ Failed to get tool state: {response.status}")

async def test_frontend_proxy_fix():
    """Test the frontend proxy fix"""
    
    print("\n🔗 Testing Frontend Proxy Fix")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        
        # Create session via frontend
        print("1️⃣ Creating session via frontend (port 3000)...")
        async with session.post("http://localhost:3000/api/sessions") as response:
            if response.status == 200:
                session_data = await response.json()
                session_id = session_data["id"] 
                print(f"✅ Created session: {session_id}")
            else:
                print(f"❌ Frontend proxy error: {response.status}")
                return
        
        # Send message via frontend proxy
        print("\n2️⃣ Sending message via frontend proxy...")
        
        payload = {
            "session_id": session_id,
            "message": "What model are you?",
            "stream": False,
            "config_override": {
                "model": "meta-llama/llama-4-maverick:free"
            }
        }
        
        print(f"📤 Frontend payload: {json.dumps(payload, indent=2)}")
        
        async with session.post("http://localhost:3000/api/chat", json=payload) as response:
            print(f"📥 Frontend response status: {response.status}")
            
            if response.status == 200:
                data = await response.json()
                response_text = data.get("response", "")
                print(f"📝 Frontend response: {response_text}")
                
                if "llama" in response_text.lower() or "maverick" in response_text.lower():
                    print("✅ SUCCESS: Frontend proxy forwarded config override correctly")
                elif "deepseek" in response_text.lower():
                    print("❌ FAILED: Frontend proxy did not forward config override")
                else:
                    print("⚠️  UNCLEAR: Need to check logs")
            else:
                error_text = await response.text()
                print(f"❌ Frontend proxy error: {error_text}")

async def main():
    print("🚀 Direct Backend Config Override Test\n")
    
    await test_backend_config_override()
    await test_frontend_proxy_fix()
    
    print("\n🎯 Test Complete!")

if __name__ == "__main__":
    asyncio.run(main()) 