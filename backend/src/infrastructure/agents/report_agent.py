import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_aws import ChatBedrock
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from ..utils.logger import logger


async def report_agent(data: str, file_type: str, mime_type: str) -> str:
    """
    data: base64-encoded string of the file/image
    file_type: "image" | "file" | "audio" | "text"
    mime_type: e.g. "image/jpeg" or "application/pdf"
    """
    logger.info("Report agent invoked", file_type=file_type, mime_type=mime_type)
    
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
            # "anthropic.claude-3-haiku-20240307-v1:0",
            "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
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
            "You are a medical data extraction specialist. "
            "Your ONLY task is to extract information that is explicitly present in the medical report. "
            "DO NOT add any interpretations, insights, recommendations, or assessments that are not in the document. "
            "DO NOT infer normal/abnormal ranges unless stated in the report. "
            "DO NOT provide medical advice or clinical opinions. \n\n"
            "Output the extracted data in this JSON structure:\n"
            "{\n"
            "  \"resourceType\": \"DiagnosticReport\",\n"
            "  \"status\": \"final\",\n"
            "  \"effectiveDateTime\": \"YYYY-MM-DD\" (if date is in report),\n"
            "  \"result\": [\n"
            "    {\n"
            "      \"testName\": \"Test name as written\",\n"
            "      \"value\": \"Exact value with unit\",\n"
            "      \"referenceRange\": \"Range if stated in report\",\n"
            "      \"interpretation\": \"Only if explicitly stated\"\n"
            "    }\n"
            "  ],\n"
            "  \"clinicalFindings\": [\"Finding 1\", \"Finding 2\"],\n"
            "  \"diagnosticImpressions\": [\"Impression 1\"] (only if stated)\n"
            "}\n\n"
            "Rules:\n"
            "- Extract exact values, dates, and measurements as written\n"
            "- Preserve medical terminology from the document\n"
            "- If a field has no data in the report, use empty array [] or omit it\n"
            "- Do not add reference ranges unless they are in the report\n"
            "- Do not interpret or explain findings\n"
            "- Output ONLY valid JSON, no markdown formatting"
        )
    }

    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Extract all data from this medical report and output as JSON following the exact structure specified."},
            {
                "type": file_type,
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
        
        logger.info("Report agent completed successfully", file_type=file_type, mime_type=mime_type)
        return response.text() if hasattr(response, "text") else str(response)
    except Exception as e:
        logger.error("Report agent model invocation failed", error=str(e), exception_type=type(e).__name__, file_type=file_type)
        return f"Model invocation failed: {str(e)}"
