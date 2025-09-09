#!/usr/bin/env python3
"""
Final test to verify frontend proxy config override and session creation fix
"""

import asyncio
import aiohttp
import json

async def test_frontend_complete_flow():
    """Test complete frontend flow with config override"""
    
    print("🎯 Testing Complete Frontend Config Override Flow")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        
        # Step 1: Test session creation through frontend proxy
        print("1️⃣ Testing session creation through frontend proxy...")
        session_payload = {"name": "Config Override Test Session"}
        
        async with session.post("http://localhost:3000/api/sessions", json=session_payload) as response:
            print(f"   Status: {response.status}")
            if response.status == 200:
                session_data = await response.json()
                session_id = session_data["id"]
                print(f"   ✅ Session created: {session_id}")
            else:
                print(f"   ❌ Session creation failed: {await response.text()}")
                return
        
        print()
        
        # Step 2: Test first message with model override (the original issue!)
        print("2️⃣ Testing first message with config override...")
        chat_payload = {
            "session_id": session_id,
            "message": "Hello! Please tell me what model you are.",
            "stream": False,
            "config_override": {
                "model": "openrouter/cypher-alpha:free"
            }
        }
        
        async with session.post("http://localhost:3000/api/chat", json=chat_payload) as response:
            print(f"   Status: {response.status}")
            if response.status == 200:
                response_data = await response.json()
                
                # Extract the assistant's response (correct format with choices)
                model_used = response_data.get("model", "unknown")
                choices = response_data.get("choices", [])
                if choices:
                    assistant_message = choices[0].get("message", {})
                    content = assistant_message.get("content", "")
                    print(f"   ✅ Response received ({len(content)} chars)")
                    print(f"   📝 Content preview: {content[:100]}...")
                    print(f"   🤖 Model used: {model_used}")
                    
                    # Check if it mentions the correct model
                    if "cypher" in content.lower() or "alpha" in content.lower():
                        print(f"   🎯 ✅ CORRECT MODEL DETECTED! Model switch worked!")
                    else:
                        print(f"   ⚠️  Model unclear from response")
                        
                else:
                    print(f"   ❌ No choices in response")
            else:
                error_text = await response.text()
                print(f"   ❌ Chat failed: {error_text}")
                return
        
        print()
        
        # Step 3: Verify session state through backend
        print("3️⃣ Verifying session state in backend...")
        async with session.get(f"http://localhost:8001/sessions/{session_id}") as response:
            if response.status == 200:
                session_data = await response.json()
                
                # Check multiple locations where model is stored
                config_model = session_data.get("session_data", {}).get("config", {}).get("model", "unknown")
                metadata_model = session_data.get("session_data", {}).get("metadata", {}).get("model", "unknown")
                state_model = session_data.get("session_data", {}).get("session_state", {}).get("current_model", "unknown")
                
                print(f"   📊 Config model: {config_model}")
                print(f"   📊 Metadata model: {metadata_model}")
                print(f"   📊 Session state model: {state_model}")
                
                # Check if any model location has the correct value
                expected_model = "openrouter/cypher-alpha:free"
                if any(model == expected_model for model in [config_model, metadata_model, state_model]):
                    print(f"   ✅ PERFECT! Database shows correct model in multiple locations")
                else:
                    print(f"   ❌ Database shows wrong models: config={config_model}, metadata={metadata_model}, state={state_model}")
            else:
                print(f"   ❌ Failed to get session: {response.status}")
                
        print()
        print("🏁 Test Complete!")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_frontend_complete_flow()) 