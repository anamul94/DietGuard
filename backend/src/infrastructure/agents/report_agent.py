import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_aws import ChatBedrock


async def report_agent(data: str, type: str, mime_type: str) -> str:
    """
    data: base64-encoded string of the file/image
    type: "image" | "file" | "audio" | "text"
    mime_type: e.g. "image/jpeg" or "application/pdf"
    """
    # Load environment variables
    load_dotenv()

    # Check if env variables are loaded
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    if not all([aws_key, aws_secret, aws_region]):
        return f"Environment variables not loaded. AWS_ACCESS_KEY_ID: {'✓' if aws_key else '✗'}, AWS_SECRET_ACCESS_KEY: {'✓' if aws_secret else '✗'}, AWS_REGION: {'✓' if aws_region else '✗'}"

    try:
        llm = init_chat_model(
            "anthropic.claude-3-haiku-20240307-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
        )
    except Exception as e:
        return f"Model initialization failed: {str(e)}"

    # llm = ChatBedrock(
    #     model_id="anthropic.claude-3-haiku-20240307-v1:0",
    #     # plus AWS credentials / region etc if needed
    #     beta_use_converse_api=True,
    # )

    system_message = {
        "role": "system",
        "content": (
            "You are a medical data extraction expert with deep knowledge of laboratory tests, radiology, and pathology. "
            "You are given a medical report (e.g., blood test, imaging report, pathology report, or clinical note). "
            "Your task is to carefully analyze the content and extract all relevant medical information in a structured, "
            "machine-readable format suitable for integration into an Electronic Health Record (EHR) system. "
            "This includes patient identifiers (if available), test names, values, units, reference ranges, impressions, "
            "diagnoses, and recommendations. Ensure that:\n"
            "- Output is structured and standardized ( EHR-compatible format).\n"
            "- Medical terminology is accurate and consistent.\n"
            "- No clinical interpretation beyond the report is added (only extract what's present).\n"
            "- Preserve all numerical values, units, and ranges exactly as reported.\n"
            "- If some fields are missing, return them as null."
        )
    }


    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Extract all clinically relevant information."},
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
        # run blocking call in a thread-safe way
        response = await asyncio.to_thread(
            lambda: llm.invoke([system_message, message])
        )
        return response.text() if hasattr(response, "text") else str(response)
    except Exception as e:
        return f"Model invocation failed: {str(e)}"
