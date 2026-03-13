import asyncio
from ..utils.logger import logger
from ..utils.bedrock_utils import create_bedrock_chat_model

async def test_agent() -> str:
    """Simple test agent to check LLM connectivity"""
    logger.info("Test agent invoked")
    
    try:
        llm = create_bedrock_chat_model()
        
        message = {"role": "user", "content": "How are you?"}
        
        response = await asyncio.to_thread(lambda: llm.invoke([message]))
        
        logger.info("Test agent completed successfully")
        return response.content
    except Exception as e:
        logger.error("Test agent failed", error=str(e), exception_type=type(e).__name__)
        return f"Error: {str(e)}"
