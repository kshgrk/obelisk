#!/usr/bin/env python3
"""
Direct OpenRouter API test to identify the Mistral model issue
"""

import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv

load_dotenv()

async def test_openrouter_direct():
    """Test OpenRouter API directly with different models"""
    
    api_key = os.getenv("OPENROUTER_KEY")
    if not api_key:
        print("❌ OPENROUTER_KEY not found in environment")
        return
    
    base_url = "https://openrouter.ai/api/v1"
    
    models_to_test = [
        "mistralai/mistral-small-3.2-24b-instruct:free",
        "anthropic/claude-3-5-haiku:beta",
        "deepseek/deepseek-chat-v3-0324:free"
    ]
    
    test_message = "Hello, this is a test message to check if you're responding correctly."
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-app/obelisk",
        "X-Title": "Obelisk Debug Test"
    }
    
    async with aiohttp.ClientSession() as session:
        for model in models_to_test:
            print(f"\n🧪 Testing model: {model}")
            print("=" * 50)
            
            # Test non-streaming first
    payload = {
        "model": model,
        "messages": [
                    {"role": "user", "content": test_message}
        ],
                "temperature": 0.7,
                "max_tokens": 100,
                "stream": False
            }
            
            try:
                async with session.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    
                    print(f"Status: {response.status}")
        
                    if response.status == 200:
                        data = await response.json()
                        
                        if "choices" in data and data["choices"]:
                            content = data["choices"][0]["message"]["content"]
                            usage = data.get("usage", {})
        
                            print(f"✅ Response received: {len(content)} chars")
                            print(f"Content: {repr(content[:100])}")
                            print(f"Usage: {usage}")
                            
                            if not content.strip():
                                print("⚠️  EMPTY RESPONSE DETECTED!")
                                print(f"Full response: {json.dumps(data, indent=2)}")
                        else:
                            print("❌ No choices in response")
                            print(f"Response: {await response.text()}")
        else:
                        error_text = await response.text()
                        print(f"❌ HTTP Error {response.status}: {error_text}")
        
    except Exception as e:
                print(f"❌ Exception: {e}")
            
            # Also test streaming
            print(f"\n🌊 Testing streaming for {model}:")
            payload["stream"] = True
            
            try:
                async with session.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    
                    print(f"Streaming Status: {response.status}")
                    
                    if response.status == 200:
                        content_received = ""
                        chunk_count = 0
                        
                        async for line in response.content:
                            line_str = line.decode('utf-8').strip()
                            
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]
                                
                                if data_str == '[DONE]':
                                    break
                                
                                try:
                                    chunk_data = json.loads(data_str)
                                    
                                    if "choices" in chunk_data and chunk_data["choices"]:
                                        delta = chunk_data["choices"][0].get("delta", {})
                                        chunk_content = delta.get("content", "")
                                        
                                        if chunk_content:
                                            content_received += chunk_content
                                            chunk_count += 1
                                            
                                except json.JSONDecodeError:
                                    continue
                        
                        print(f"✅ Streaming completed: {len(content_received)} chars in {chunk_count} chunks")
                        print(f"Content: {repr(content_received[:100])}")
                        
                        if not content_received.strip():
                            print("⚠️  EMPTY STREAMING RESPONSE DETECTED!")
                    else:
                        error_text = await response.text()
                        print(f"❌ Streaming HTTP Error {response.status}: {error_text}")
                        
            except Exception as e:
                print(f"❌ Streaming Exception: {e}")
    
            print("\n" + "=" * 50)

if __name__ == "__main__":
    asyncio.run(test_openrouter_direct()) 