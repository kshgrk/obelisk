#!/usr/bin/env python3
"""
Sample fix for Mistral streaming issue
This demonstrates how to handle the OpenRouter Mistral streaming bug
"""

def should_use_streaming(model_id: str) -> bool:
    """
    Determine if streaming should be used for a given model
    
    Args:
        model_id: The model identifier
        
    Returns:
        bool: True if streaming should be used, False otherwise
    """
    
    # Known problematic models with streaming issues on OpenRouter
    problematic_streaming_models = [
        "mistralai/mistral-small-3.2-24b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        # Add other problematic models as discovered
    ]
    
    # Check if model has streaming issues
    for problematic_model in problematic_streaming_models:
        if problematic_model in model_id:
            return False
    
    return True

def get_safe_streaming_config(model_id: str, requested_streaming: bool = True) -> dict:
    """
    Get safe streaming configuration for a model
    
    Args:
        model_id: The model identifier
        requested_streaming: Whether streaming was originally requested
        
    Returns:
        dict: Configuration with appropriate streaming setting
    """
    
    use_streaming = should_use_streaming(model_id) and requested_streaming
    
    config = {
        "streaming": use_streaming,
        "reason": "streaming_supported" if use_streaming else "streaming_disabled_for_model"
    }
    
    if not use_streaming and requested_streaming:
        config["warning"] = f"Streaming disabled for {model_id} due to known OpenRouter issues"
    
    return config

# Example usage in workflow:
def prepare_api_request(model_id: str, messages: list, requested_streaming: bool = True) -> dict:
    """Prepare API request with safe streaming configuration"""
    
    streaming_config = get_safe_streaming_config(model_id, requested_streaming)
    
    request = {
        "model": model_id,
        "messages": messages,
        "stream": streaming_config["streaming"]
    }
    
    # Log warning if streaming was disabled
    if "warning" in streaming_config:
        print(f"⚠️  {streaming_config['warning']}")
    
    return request

# Example integration in SimpleStreamingChatWorkflow:
"""
In src/temporal/workflows/simple_chat.py, modify the API request preparation:

# Before:
api_request = {
    "model": model,
    "messages": openrouter_messages,
    "temperature": temperature,
    "max_tokens": max_tokens,
    "stream": streaming,
    "session_id": session_id
}

# After:
streaming_config = get_safe_streaming_config(model, streaming)
api_request = {
    "model": model,
    "messages": openrouter_messages,
    "temperature": temperature,
    "max_tokens": max_tokens,
    "stream": streaming_config["streaming"],
    "session_id": session_id
}

# Log if streaming was disabled
if "warning" in streaming_config:
    workflow.logger.warning(streaming_config["warning"])
"""

if __name__ == "__main__":
    # Test the functions
    test_models = [
        "mistralai/mistral-small-3.2-24b-instruct:free",
        "anthropic/claude-3-5-haiku:beta",
        "deepseek/deepseek-chat-v3-0324:free"
    ]
    
    print("🧪 Testing streaming configuration for different models:")
    print("=" * 60)
    
    for model in test_models:
        config = get_safe_streaming_config(model, requested_streaming=True)
        print(f"Model: {model}")
        print(f"  Streaming: {config['streaming']}")
        print(f"  Reason: {config['reason']}")
        if "warning" in config:
            print(f"  Warning: {config['warning']}")
        print() 