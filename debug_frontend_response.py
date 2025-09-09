#!/usr/bin/env python3
"""
Debug script to examine the actual frontend response structure
"""

import asyncio
import aiohttp
import json

async def debug_frontend_response():
    """Debug the actual frontend response structure"""
    
    print("🔍 Debugging Frontend Response Structure")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        
        # Step 1: Create session
        print("1️⃣ Creating session...")
        session_payload = {"name": "Debug Session"}
        
        async with session.post("http://localhost:3000/api/sessions", json=session_payload) as response:
            if response.status == 200:
                session_data = await response.json()
                session_id = session_data["id"]
                print(f"✅ Session: {session_id}")
            else:
                print(f"❌ Failed: {await response.text()}")
                return
        
        # Step 2: Send chat message and examine full response
        print("\n2️⃣ Sending chat message...")
        chat_payload = {
            "session_id": session_id,
            "message": "Hello! What model are you?",
            "stream": False,
            "config_override": {
                "model": "openrouter/cypher-alpha:free"
            }
        }
        
        async with session.post("http://localhost:3000/api/chat", json=chat_payload) as response:
            print(f"Status: {response.status}")
            
            if response.status == 200:
                response_data = await response.json()
                print(f"\n📋 FULL RESPONSE STRUCTURE:")
                print(json.dumps(response_data, indent=2))
                
                # Examine the structure
                print(f"\n🔍 ANALYSIS:")
                print(f"Top-level keys: {list(response_data.keys())}")
                
                if "messages" in response_data:
                    messages = response_data["messages"]
                    print(f"Messages array length: {len(messages)}")
                    if messages:
                        print(f"Last message keys: {list(messages[-1].keys())}")
                        print(f"Last message content: {messages[-1].get('content', 'NO CONTENT')[:100]}...")
                else:
                    print("❌ No 'messages' key found!")
                    
            else:
                error_text = await response.text()
                print(f"❌ Error: {error_text}")
        
        # Step 3: Check backend session directly
        print(f"\n3️⃣ Checking backend session...")
        async with session.get(f"http://localhost:8001/sessions/{session_id}") as response:
            if response.status == 200:
                backend_data = await response.json()
                print(f"Backend model: {backend_data.get('metadata', {}).get('model', 'UNKNOWN')}")
                print(f"Message count: {backend_data.get('message_count', 0)}")
            else:
                print(f"Backend error: {response.status}")

if __name__ == "__main__":
    asyncio.run(debug_frontend_response()) 