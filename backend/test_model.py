#!/usr/bin/env python3
"""
Test script to verify the Global Anthropic Claude Sonnet 4.6 model is working correctly.
"""

import asyncio
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from infrastructure.utils.bedrock_utils import create_bedrock_chat_model, DEFAULT_BEDROCK_MODEL
from infrastructure.utils.logger import logger

async def test_model():
    """Test the model configuration and basic functionality."""
    try:
        print(f"Testing model: {DEFAULT_BEDROCK_MODEL}")
        
        # Create the model
        llm = create_bedrock_chat_model(temperature=0.1)
        print("✓ Model created successfully")
        
        # Test a simple message
        message = {"role": "user", "content": "Hello! Please respond with 'Model test successful' if you can read this."}
        
        print("Sending test message...")
        response = await asyncio.to_thread(lambda: llm.invoke([message]))
        
        response_text = response.content if hasattr(response, 'content') else str(response)
        print(f"✓ Response received: {response_text}")
        
        # Check metadata
        if hasattr(response, 'response_metadata'):
            meta = response.response_metadata
            print(f"✓ Model name: {meta.get('model_name', 'unknown')}")
        
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            print(f"✓ Token usage - Input: {usage.get('input_tokens', 0)}, Output: {usage.get('output_tokens', 0)}")
        
        print("✅ Model test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Model test failed: {str(e)}")
        logger.error("Model test failed", error=str(e), exception_type=type(e).__name__)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_model())
    sys.exit(0 if success else 1)