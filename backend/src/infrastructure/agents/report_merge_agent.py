"""
Report Merge Agent

Intelligently merges old and new medical reports, tracking history and maintaining data integrity.
"""

import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from ..utils.logger import logger
from .agent_response import AgentResponse
from typing import Dict, Any
import json


async def report_merge_agent(
    old_report: Dict[str, Any],
    new_report: Dict[str, Any],
    patient_info: Dict[str, Any] = None
) -> AgentResponse:
    """
    Merge old and new medical reports intelligently.
    
    Args:
        old_report: Existing report data (extracted analysis)
        new_report: Newly extracted report data
        patient_info: Optional patient information (name, age, etc.)
        
    Returns:
        AgentResponse with merged report in EHR format
    """
    logger.info("Report merge agent invoked", 
               has_old_report=bool(old_report),
               has_new_report=bool(new_report))
    
    # Load environment variables
    load_dotenv()

    # Check if env variables are loaded
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    if not all([aws_key, aws_secret, aws_region]):
        logger.error("Report merge agent configuration error - missing AWS credentials")
        return AgentResponse.error_response("Configuration error. Please try again later.")

    try:
        llm = init_chat_model(
            "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
            temperature=0.2,  # Low temperature for consistent merging
        )
    except Exception as e:
        logger.error("Report merge agent LLM initialization failed", error=str(e))
        return AgentResponse.error_response("Report merge service is temporarily unavailable.")

    system_message = {
        "role": "system",
        "content": (
            "You are a medical data integration specialist responsible for merging medical reports. "
            "Your task is to create a comprehensive Electronic Health Record (EHR) by intelligently merging "
            "old and new medical reports.\n\n"
            "**MERGING RULES:**\n"
            "1. For overlapping test results (e.g., both reports have RBC count): Use the NEW value as current, keep OLD value in history\n"
            "2. For non-overlapping data: Include both in the merged report\n"
            "3. Maintain chronological order and track changes\n"
            "4. Preserve all clinical findings from both reports\n"
            "5. Clearly distinguish between current values and historical values\n\n"
            "**OUTPUT FORMAT (Simplified FHIR-inspired JSON):**\n"
            "```json\n"
            "{\n"
            "  \"resourceType\": \"DiagnosticReport\",\n"
            "  \"status\": \"final\",\n"
            "  \"category\": \"Laboratory/Imaging/Other\",\n"
            "  \"effectiveDateTime\": \"YYYY-MM-DD\",\n"
            "  \"issued\": \"YYYY-MM-DDTHH:MM:SSZ\",\n"
            "  \"result\": [\n"
            "    {\n"
            "      \"testName\": \"RBC Count\",\n"
            "      \"value\": \"4.8 million/mcL\",\n"
            "      \"unit\": \"million/mcL\",\n"
            "      \"referenceRange\": \"4.5-5.5\",\n"
            "      \"status\": \"normal/abnormal/critical\",\n"
            "      \"interpretation\": \"Brief clinical interpretation\",\n"
            "      \"history\": [\n"
            "        {\"date\": \"2025-12-01\", \"value\": \"4.5 million/mcL\", \"status\": \"normal\"},\n"
            "        {\"date\": \"2025-12-26\", \"value\": \"4.8 million/mcL\", \"status\": \"normal\"}\n"
            "      ]\n"
            "    }\n"
            "  ],\n"
            "  \"clinicalFindings\": \"Summary of all clinical findings\",\n"
            "  \"diagnosticImpressions\": \"Overall diagnostic assessment\",\n"
            "  \"mergeInfo\": {\n"
            "    \"mergedAt\": \"YYYY-MM-DDTHH:MM:SSZ\",\n"
            "    \"previousReportDate\": \"YYYY-MM-DD\",\n"
            "    \"newReportDate\": \"YYYY-MM-DD\",\n"
            "    \"testsUpdated\": [\"RBC\", \"Hemoglobin\"],\n"
            "    \"testsAdded\": [\"Platelet Count\"]\n"
            "  }\n"
            "}\n"
            "```\n\n"
            "**IMPORTANT:** Return ONLY the JSON object, no additional text or markdown formatting."
        ),
    }

    # Prepare patient context
    patient_context = ""
    if patient_info:
        patient_context = f"\\n**Patient Information:**\\n{json.dumps(patient_info, indent=2)}\\n"

    user_message = {
        "role": "user",
        "content": (
            f"**OLD REPORT (Previous Medical Data):**\\n"
            f"```json\\n{json.dumps(old_report, indent=2)}\\n```\\n\\n"
            f"**NEW REPORT (Recently Uploaded):**\\n"
            f"```json\\n{json.dumps(new_report, indent=2)}\\n```\\n"
            f"{patient_context}\\n"
            "Merge these reports following the rules. For any test that appears in both reports, "
            "use the new value as current and add the old value to history. "
            "Include all unique tests from both reports. "
            "Return the merged EHR in the specified JSON format."
        ),
    }

    try:
        # Run blocking call in a thread-safe way with Langfuse tracing
        response = await asyncio.to_thread(
            lambda: llm.invoke([system_message, user_message], config={"callbacks": [get_langfuse_handler()]})
        )
        
        # Flush events to Langfuse
        flush_langfuse()
        
        # Extract metadata
        meta = response.response_metadata if hasattr(response, 'response_metadata') else {}
        usage = response.usage_metadata if hasattr(response, 'usage_metadata') else {}
        
        # Prepare metadata for token tracking
        metadata = {
            "model_name": meta.get("model_name", "unknown"),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cache_creation_tokens": usage.get("input_token_details", {}).get("cache_creation", 0),
            "cache_read_tokens": usage.get("input_token_details", {}).get("cache_read", 0),
        }
        
        # Get response text
        response_text = response.text() if hasattr(response, "text") else str(response)
        
        # Try to parse as JSON to validate
        try:
            # Remove markdown code blocks if present
            if response_text.strip().startswith("```"):
                response_text = response_text.strip()
                # Remove first line (```json or ```)
                lines = response_text.split("\\n")
                response_text = "\\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            
            merged_report = json.loads(response_text)
            logger.info("Report merge agent completed successfully", 
                       has_merge_info=bool(merged_report.get("mergeInfo")))
            
            return AgentResponse.success_response(merged_report, metadata=metadata)
        except json.JSONDecodeError as je:
            logger.warning("Failed to parse merged report as JSON, returning as text", error=str(je))
            return AgentResponse.success_response(response_text, metadata=metadata)
            
    except Exception as e:
        logger.error("Report merge agent model invocation failed", error=str(e), exception_type=type(e).__name__)
        return AgentResponse.error_response("Unable to merge reports at this time. Please try again later.")
