import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_aws import ChatBedrock
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from ..utils.logger import logger


async def report_agent(data: str, type: str, mime_type: str) -> str:
    """
    data: base64-encoded string of the file/image
    type: "image" | "file" | "audio" | "text"
    mime_type: e.g. "image/jpeg" or "application/pdf"
    """
    logger.info("Report agent invoked", file_type=type, mime_type=mime_type)
    
    # Load environment variables
    load_dotenv()

    # Check if env variables are loaded
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    if not all([aws_key, aws_secret, aws_region]):
        logger.error("Report agent configuration error - missing AWS credentials",
                    has_key=bool(aws_key), has_secret=bool(aws_secret), has_region=bool(aws_region))
        return f"Environment variables not loaded. AWS_ACCESS_KEY_ID: {'✓' if aws_key else '✗'}, AWS_SECRET_ACCESS_KEY: {'✓' if aws_secret else '✗'}, AWS_REGION: {'✓' if aws_region else '✗'}"

    try:
        llm = init_chat_model(
            "anthropic.claude-3-haiku-20240307-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
        )
    except Exception as e:
        logger.error("Report agent LLM initialization failed", error=str(e), exception_type=type(e).__name__)
        return f"Model initialization failed: {str(e)}"

    # llm = ChatBedrock(
    #     model_id="anthropic.claude-3-haiku-20240307-v1:0",
    #     # plus AWS credentials / region etc if needed
    #     beta_use_converse_api=True,
    # )

    system_message = {
        "role": "system",
        "content": (
            "You are Dr. Maria Chen, a licensed physician specializing in diagnostic medicine and laboratory analysis. "
            "Review medical reports and provide professional medical assessment. "
            "Never mention AI, image analysis, or technology - respond as a practicing doctor. "
            "Extract and interpret medical information professionally. \n\n"
            "Provide assessment in this format:\n"
            "**CLINICAL FINDINGS**\n"
            "**LABORATORY RESULTS**\n"
            "**DIAGNOSTIC IMPRESSIONS**\n"
            "Maintain professional medical terminology and clinical accuracy."
            "**Output in markdown format with headings and bullet points where appropriate."
            "**Highlight critical findings clearly."
            "Highlight key values in the LABORATORY RESULTS section."
            "No need MEDICAL RECOMMENDATIONS, FOLLOW-UP REQUIREMENTS just extract information"
        )
    }

    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Extract all clinically relevant information. and show info in a structured format."},
            {
                "type": type,
                "source_type": "base64",
                "mime_type": mime_type,
                "data": data,
                "name": "report"
            },
        ],
    }

    try:
        # run blocking call in a thread-safe way with Langfuse tracing
        response = await asyncio.to_thread(
            lambda: llm.invoke([system_message, message], config={"callbacks": [get_langfuse_handler()]})
        )
        
        # Flush events to Langfuse
        flush_langfuse()
        
        logger.info("Report agent completed successfully", file_type=type, mime_type=mime_type)
        return response.text() if hasattr(response, "text") else str(response)
    except Exception as e:
        logger.error("Report agent model invocation failed", error=str(e), exception_type=type(e).__name__, file_type=type)
        return f"Model invocation failed: {str(e)}"
