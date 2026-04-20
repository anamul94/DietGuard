import asyncio

from ..utils.logger import logger
from ..utils.bedrock_utils import create_llm, get_chat_model_diagnostics
from ..utils.nutrition_utils import metric_value
from .agent_response import AgentResponse
from ...presentation.schemas.food_schemas import FoodAnalysis


async def food_agent(data, content_type, mime_type, location=None):
    """
    Analyze food images and return structured nutritional data.
    
    Args:
        data: base64-encoded string OR list of base64 strings for multiple images
        content_type: "image" OR list of "image" for multiple images
        mime_type: e.g. "image/jpeg" OR list of mime types for multiple images
        location: Optional user location (e.g., "Mumbai, India") for regional food context
        
    Returns:
        AgentResponse with structured FoodAnalysis data
    """
    image_count = len(data) if isinstance(data, list) else 1
    logger.info("Food agent invoked", image_count=image_count)
    
    try:
        diagnostics = get_chat_model_diagnostics(agent_name="food_agent")
        llm = create_llm(agent_name="food_agent", temperature=0.1)
        # Apply structured output schema with raw response for metadata
        structured_llm = llm.with_structured_output(FoodAnalysis, include_raw=True)
    except Exception as e:
        logger.error(
            "Food agent LLM initialization failed",
            error=str(e),
            exception_type=type(e).__name__,
            diagnostics=diagnostics if "diagnostics" in locals() else None,
        )
        return AgentResponse.error_response("Food analysis service is temporarily unavailable. Please try again later.")

    # Build location context if available
    location_context = ""
    if location:
        location_context = (
            f"\n\n**USER LOCATION CONTEXT:**"
            f"\nThe user is located in {location}. Consider local and street food common in this region when identifying items. "
            f"Be aware of regional specialties, traditional dishes, and popular street food from this area."
        )
    
    system_message = {
        "role": "system",
        "content": (
            "CRITICAL: All your responses must be in English only. No other language is permitted.\n\n"
            "You are Dr. James Rodriguez, a certified nutritionist and food analyst. "
            "Your task is to identify and analyze FOOD ITEMS in images. "
            "This agent is DESIGNED ONLY for food images: meals, dishes, restaurant food, grocery items, cooking ingredients, etc.\n\n"
            "REJECTION RULES - If the uploaded image is NOT food, return this exact JSON:\n"
            '{"error": true, "message": "This does not appear to be a food image. Please upload a photo of a meal, dish, or food item."}\n\n'
            "DO NOT analyze medical reports, prescriptions, lab reports, radiology images, documents, or any non-food content. "
            "If the image shows medical documents, text files, receipts, or anything similar, reject it with the error JSON above.\n\n"
            "ACCEPTED CONTENT:\n"
            "- Meals (breakfast, lunch, dinner, snacks)\n"
            "- Restaurant dishes and plated food\n"
            "- Groceries and shopping items\n"
            "- Cooking ingredients and raw food\n"
            "- Food packaging (if showing food items)\n"
            "- Beverages and drinks\n\n"
            "REJECTED CONTENT (return error JSON):\n"
            "- Medical reports, lab results, prescriptions\n"
            "- Radiology images (X-ray, MRI, CT)\n"
            "- Documents, receipts, certificates\n"
            "- Non-food products or items\n\n"
            "If you are unsure whether it's a food image, lean towards rejecting it.\n\n"
            f"{location_context}"
            "\n\nIMPORTANT INSTRUCTIONS:"
            "\n1. Identify ONLY EDIBLE FOOD ITEMS visible in the image(s)"
            "\n2. **EXCLUDE ALL NON-FOOD ITEMS:** Do NOT include cooking equipment (charcoal, grills, stoves), "
            "utensils (plates, bowls, forks, spoons, knives), serving ware, napkins, decorations, or any other non-edible items"
            "\n3. For each food item, provide a DETAILED description that includes:"
            "\n   - The main food item name"
            "\n   - Visible ingredients, toppings, or components"
            "\n   - Preparation method if identifiable (grilled, fried, boiled, baked, etc.)"
            "\n   - Examples: 'pizza with cheese and tomato', 'grilled chicken with naan roti', "
            "'caesar salad with croutons and parmesan cheese', 'fried rice with vegetables and egg', 'seekh kabab'"
            "\n4. Group toppings, fillings, garnish salad, sauces, dips, or plate decoration into the main item unless they are clearly separate servings"
            "\n5. Return only the distinct meal items a user would realistically confirm in a food log"
            "\n6. Focus exclusively on EDIBLE food items — ignore people, utensils, backgrounds, cooking equipment, or any non-food elements"
            "\n7. Provide item-level nutrition for each identified food item in `fooditem_details`"
            "\n8. Provide accurate nutritional estimates for the TOTAL meal (sum of all items) in `nutrition`"
            "\n8. Return nutrition fields as structured objects with value and unit."
            "\n   Example: calories = {\"value\": 320, \"unit\": \"kcal\"}, protein = {\"value\": 12, \"unit\": \"g\"}"
            "\n9. `fooditem_details` is the source of truth and must include the item name, optional quantity/preparation, and that item's nutrition."
            "\n10. Be objective and precise — do not speculate or include unnecessary commentary"
        ),
    }

    # Handle multiple images
    if isinstance(data, list):
        content = [{
            "type": "text", 
            "text": "Identify and analyze all food items in these images. Provide per-item nutrition in fooditem_details and total meal nutrition in nutrition."
        }]
        for i, (img_data, img_type, img_mime) in enumerate(zip(data, content_type, mime_type)):
            content.append({
                "type": img_type,
                "source_type": "base64",
                "mime_type": img_mime,
                "data": img_data,
            })
    else:
        content = [
            {"type": "text", "text": "Identify and analyze all food items in this image. Provide per-item nutrition in fooditem_details and total meal nutrition in nutrition."},
            {
                "type": content_type,
                "source_type": "base64",
                "mime_type": mime_type,
                "data": data,
            },
        ]

    message = {
        "role": "user",
        "content": content,
    }

    try:
        # Invoke with structured output (returns dict with 'parsed' and 'raw')
        result = await asyncio.to_thread(
            lambda: structured_llm.invoke([system_message, message])
        )

        # Extract parsed data and metadata
        parsed: FoodAnalysis = result["parsed"]
        raw = result["raw"]  # AIMessage with metadata
        meta = raw.response_metadata if hasattr(raw, 'response_metadata') else {}
        usage = raw.usage_metadata if hasattr(raw, 'usage_metadata') else {}

        # parsed=None means the LLM returned something that doesn't match FoodAnalysis
        # (e.g. the rejection JSON {"error": true, "message": "..."} for non-food images)
        if parsed is None:
            import json as _json
            raw_content = raw.content if hasattr(raw, 'content') else ""
            try:
                error_payload = _json.loads(raw_content) if isinstance(raw_content, str) else {}
                user_message = error_payload.get("message") or "This does not appear to be a food image. Please upload a photo of a meal, dish, or food item."
            except Exception:
                user_message = "Unable to analyze food items at this time. Please try again later."
            logger.warning("Food agent returned unparseable response",
                           image_count=image_count,
                           parsing_error=str(result.get("parsing_error")),
                           raw_content=raw_content[:200] if isinstance(raw_content, str) else "")
            return AgentResponse.error_response(user_message)

        # Convert Pydantic model to dict for AgentResponse
        structured_data = parsed.model_dump()
        
        # Prepare metadata for token tracking
        metadata = {
            "model_name": meta.get("model_name", "unknown"),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cache_creation_tokens": usage.get("input_token_details", {}).get("cache_creation", 0),
            "cache_read_tokens": usage.get("input_token_details", {}).get("cache_read", 0),
        }
        
        logger.info("Food agent completed successfully", 
                   image_count=image_count,
                   food_items_count=len(structured_data.get('fooditem_details', [])),
                   total_calories=metric_value(structured_data.get('nutrition', {}).get('calories')) or 0,
                   token_usage=usage)
        
        return AgentResponse.success_response(structured_data, metadata=metadata)
            
    except Exception as e:
        logger.error("Food agent model invocation failed", 
                    error=str(e), 
                    exception_type=e.__class__.__name__, 
                    image_count=image_count)
        return AgentResponse.error_response("Unable to analyze food items at this time. Please try again later.")
