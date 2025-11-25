import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from ..utils.logger import logger

async def test_agent() -> str:
    """Simple test agent to check LLM connectivity"""
    logger.info("Test agent invoked")
    load_dotenv()
    
    aws_region = os.getenv("AWS_REGION")
    
    try:
        llm = init_chat_model(
            "anthropic.claude-3-haiku-20240307-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
        )
        
        message = {"role": "user", "content": "How are you?"}
        
        response = await asyncio.to_thread(lambda: llm.invoke([message]))
        
        logger.info("Test agent completed successfully")
        return response.content
    except Exception as e:
        logger.error("Test agent failed", error=str(e), exception_type=type(e).__name__)
        return f"Error: {str(e)}"