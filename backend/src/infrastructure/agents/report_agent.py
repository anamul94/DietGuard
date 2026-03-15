import asyncio

from ..utils.logger import logger
from ..utils.bedrock_utils import create_chat_model, get_chat_model_diagnostics
from .agent_response import AgentResponse


async def report_agent(data: str, file_type: str, mime_type: str) -> AgentResponse:
    """
    data: base64-encoded string of the file/image
    file_type: "image" | "file" | "audio" | "text"
    mime_type: e.g. "image/jpeg" or "application/pdf"
    """
    logger.info("Report agent invoked", file_type=file_type, mime_type=mime_type)
    
    try:
        model_diag = get_chat_model_diagnostics(agent_name="report_agent")
        logger.info(
            "Report agent model runtime",
            **model_diag,
        )
        llm = create_chat_model(agent_name="report_agent")
    except Exception as e:
        logger.error(
            "Report agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
            diagnostics=model_diag if "model_diag" in locals() else None,
        )
        return AgentResponse.error_response("Report extraction service is temporarily unavailable.")

    system_message = {
        "role": "system",
        "content": (
            "You are a medical data extraction specialist. "
            "Your ONLY task is to extract information that is explicitly present in the medical report. "
            "Do not assume the report type in advance. The user may upload any medical document: lab report, prescription, discharge summary, consultation note, radiology report, or unknown type. "
            "DO NOT add medical interpretations, insights, recommendations, or assessments that are not in the document. "
            "DO NOT infer normal or abnormal ranges unless they are written in the document. "
            "DO NOT provide medical advice or clinical opinions.\n\n"
            "Output ONLY valid JSON in this flexible structure:\n"
            "{\n"
            "  \"documentType\": \"lab_report | prescription | discharge_summary | radiology_report | consultation_note | unknown\",\n"
            "  \"title\": \"document title if visible\",\n"
            "  \"reportDate\": \"YYYY-MM-DD if visible\",\n"
            "  \"sections\": [\n"
            "    {\n"
            "      \"name\": \"Section name as written\",\n"
            "      \"kind\": \"results | medications | diagnosis | advice | findings | history | other\",\n"
            "      \"summary\": \"short factual summary of that section using only document content\",\n"
            "      \"pageNumber\": 1\n"
            "    }\n"
            "  ],\n"
            "  \"entities\": [\n"
            "    {\n"
            "      \"entityType\": \"observation | condition | medication | allergy | restriction | recommendation | finding | procedure | encounter | other\",\n"
            "      \"category\": \"lab | diagnosis | prescription | diet | symptom | imaging | clinical_finding | advice | other\",\n"
            "      \"label\": \"entity name exactly or nearly exactly as written\",\n"
            "      \"valueText\": \"value or factual detail exactly as written\",\n"
            "      \"valueNumeric\": 7.2,\n"
            "      \"unit\": \"%\",\n"
            "      \"referenceRange\": \"4.0-5.6%\",\n"
            "      \"interpretation\": \"high if explicitly stated\",\n"
            "      \"status\": \"present/final/ongoing/etc only if explicitly stated\",\n"
            "      \"effectiveDate\": \"YYYY-MM-DD if visible\",\n"
            "      \"sourceSection\": \"section name if known\",\n"
            "      \"sourceText\": \"short supporting snippet from the document\",\n"
            "      \"pageNumber\": 1,\n"
            "      \"confidence\": 0.0,\n"
            "      \"attributes\": {\n"
            "        \"dose\": \"500 mg\",\n"
            "        \"schedule\": \"twice daily\",\n"
            "        \"timing\": \"after meals\",\n"
            "        \"panel\": \"Lipid Profile\"\n"
            "      }\n"
            "    }\n"
            "  ],\n"
            "  \"unmappedEntities\": [\n"
            "    {\n"
            "      \"label\": \"important content that does not fit a standard type\",\n"
            "      \"sourceText\": \"supporting snippet\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Prefer preserving information as entities instead of dropping it.\n"
            "- If you are unsure of the report type, set documentType to unknown.\n"
            "- Unknown or unusual report content should go into entities or unmappedEntities, not be omitted.\n"
            "- Preserve medical terminology from the document.\n"
            "- Extract exact values, units, dates, medication schedules, and advice as written.\n"
            "- If valueNumeric is not explicit, omit it.\n"
            "- If confidence is uncertain, provide a conservative decimal between 0 and 1.\n"
            "- Output ONLY valid JSON with no markdown formatting."
        )
    }

    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Extract all explicit medical information from this document into the flexible JSON structure with sections, entities, and unmappedEntities."},
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
        response = await asyncio.to_thread(
            lambda: llm.invoke([system_message, message])
        )

        # Extract metadata
        meta = response.response_metadata if hasattr(response, 'response_metadata') else {}
        usage = response.usage_metadata if hasattr(response, 'usage_metadata') else {}
        
        # Prepare metadata for token tracking
        metadata = {
            "model_name": meta.get("model_name", "claude-sonnet-4.6"),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cache_creation_tokens": usage.get("input_token_details", {}).get("cache_creation", 0),
            "cache_read_tokens": usage.get("input_token_details", {}).get("cache_read", 0),
        }
        
        # Get response text
        response_text = response.content if hasattr(response, "content") else str(response)
        
        logger.info("Report agent completed successfully", 
                   file_type=file_type, 
                   mime_type=mime_type,
                   token_usage=usage)
        
        return AgentResponse.success_response(response_text, metadata=metadata)
    except Exception as e:
        logger.error(
            "Report agent model invocation failed",
            error=str(e),
            exception_type=type(e).__name__,
            file_type=file_type,
            model_id=bedrock_diag["model_id"] if "bedrock_diag" in locals() else None,
            region_name=bedrock_diag["region_name"] if "bedrock_diag" in locals() else None,
            credential_source=bedrock_diag["credential_source"] if "bedrock_diag" in locals() else None,
            credential_type=bedrock_diag["credential_type"] if "bedrock_diag" in locals() else None,
            has_session_token=bedrock_diag["has_session_token"] if "bedrock_diag" in locals() else None,
            integration_path=bedrock_diag["integration_path"] if "bedrock_diag" in locals() else None,
        )
        return AgentResponse.error_response(f"Model invocation failed: {str(e)}")
