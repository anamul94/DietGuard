import asyncio
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
import logging
from ..utils.langfuse_utils import get_langfuse_handler, flush_langfuse
from .agent_response import AgentResponse
from ...presentation.schemas.ingredient_schemas import IngredientAnalysis


logger = logging.getLogger(__name__)

async def ingredient_scanner_agent(data, media_type, mime_type):
    """
    Analyze food packaging images to extract and analyze ingredient lists.
    
    Uses Claude vision model to:
    1. Read ingredient text from packaging images
    2. Identify each ingredient (including chemical names)
    3. Provide health ratings (red/yellow/green)
    4. Explain ingredients in simple language
    5. Flag allergens, age restrictions, and dietary concerns
    
    Args:
        data: base64-encoded image string
        type: "image"
        mime_type: e.g. "image/jpeg"
        
    Returns:
        AgentResponse with structured IngredientAnalysis data
    """
    logger.info("Ingredient scanner agent invoked")
    
    # Load environment variables
    load_dotenv()

    # Check if env variables are loaded
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    if not all([aws_key, aws_secret, aws_region]):
        logger.error("Ingredient scanner agent configuration error - missing AWS credentials", 
                    has_key=bool(aws_key), has_secret=bool(aws_secret), has_region=bool(aws_region))
        return AgentResponse.error_response("Configuration error. Please try again later.")

    try:
        llm = init_chat_model(
            "apac.anthropic.claude-sonnet-4-20250514-v1:0",
            model_provider="bedrock_converse",
            region_name=aws_region,
            temperature=0.1,
        )
        # Apply structured output schema with raw response for metadata
        structured_llm = llm.with_structured_output(IngredientAnalysis, include_raw=True)
    except Exception as e:
        logger.error("Ingredient scanner agent LLM initialization failed", error=str(e), exception_type=type(e).__name__)
        return AgentResponse.error_response("Ingredient analysis service is temporarily unavailable. Please try again later.")

    system_message = {
        "role": "system",
        "content": (
            "You are Dr. Sarah Chen, a food safety expert and toxicologist specializing in food additives and ingredient analysis. "
            "Your task is to analyze ingredient lists from food packaging images and provide clear, educational health assessments."
            "\n\n**CRITICAL INSTRUCTIONS:**"
            "\n\n**1. EXTRACT ALL INGREDIENTS:**"
            "\n   - Read the ingredient list from the packaging image carefully"
            "\n   - Identify every single ingredient listed"
            "\n   - Pay special attention to chemical names, E-numbers, INS codes, and preservatives"
            "\n\n**2. EXPLAIN IN SIMPLE LANGUAGE:**"
            "\n   - For chemical names (e.g., 'Monosodium Glutamate'), provide the common name (e.g., 'MSG')"
            "\n   - For E-numbers (e.g., 'E621'), explain what they are (e.g., 'MSG - flavor enhancer')"
            "\n   - Use language that a 12-year-old can understand"
            "\n   - Avoid technical jargon unless necessary, and always explain it"
            "\n\n**3. HEALTH RATING SYSTEM:**"
            "\n   - **GREEN**: Natural, safe, healthy ingredients (fruits, vegetables, whole grains, natural oils, vitamins)"
            "\n   - **YELLOW**: Moderate concern - generally safe but may cause issues for some people (MSG, certain preservatives, refined sugars, artificial flavors)"
            "\n   - **RED**: Harmful or should be avoided - especially by children, pregnant women, or sensitive individuals (sodium benzoate + vitamin C, artificial colors linked to hyperactivity, trans fats, certain preservatives)"
            "\n\n**4. PROVIDE TWO LEVELS OF EXPLANATION:**"
            "\n   - **Short explanation**: 1-2 sentences, quick summary"
            "\n   - **Detailed explanation**: 3-5 sentences covering what it is, why it's used, health effects, and who should avoid it"
            "\n\n**5. FLAG SPECIAL CONCERNS:**"
            "\n   - **Age restrictions**: Ingredients not suitable for children (especially under 3, 5, or 10 years)"
            "\n   - **Health conditions**: Flag ingredients harmful for patients with:"
            "\n     • Heart disease (high sodium, trans fats, saturated fats)"
            "\n     • Kidney disease (high sodium, potassium, phosphorus)"
            "\n     • Diabetes (high sugar, refined carbs, artificial sweeteners)"
            "\n     • Hypertension (high sodium, MSG)"
            "\n     • Liver disease (artificial additives, preservatives)"
            "\n   - **Dietary restrictions**: Mark if vegan, vegetarian, halal, kosher compatible"
            "\n   - **Critical warnings**: Preservatives for children, carcinogenic combinations, hyperactivity triggers"
            "\n\n**6. FOCUS ON EDUCATION:**"
            "\n   - Help people understand WHY an ingredient is rated red/yellow/green"
            "\n   - Explain health impacts in practical terms"
            "\n   - Be especially protective of children's health AND patients with chronic conditions"
            "\n   - Mention if ingredients can cause allergic reactions or sensitivity"
            "\n   - Highlight risks for heart, kidney, diabetes, and hypertension patients"
            "\n\n**7. COMMON INGREDIENTS TO WATCH:**"
            "\n   - Preservatives: Sodium benzoate (E211), Potassium sorbate (E202), BHA/BHT"
            "\n   - Flavor enhancers: MSG (E621), Disodium inosinate (E631)"
            "\n   - Artificial colors: Tartrazine (E102), Sunset Yellow (E110), Allura Red (E129)"
            "\n   - Sweeteners: Aspartame (E951), Sucralose (E955), Saccharin (E954)"
            "\n   - Emulsifiers: Lecithin (E322), Mono- and diglycerides (E471)"
            "\n   - High sodium ingredients: Salt, sodium benzoate, MSG, soy sauce"
            "\n   - High sugar ingredients: Sugar, glucose syrup, fructose, corn syrup"
            "\n\n**8. OVERALL RATING:**"
            "\n   - If ANY ingredient is RED, overall rating should be YELLOW or RED"
            "\n   - If multiple YELLOW ingredients, consider making overall RED"
            "\n   - Only GREEN if all ingredients are natural and safe"
            "\n\n**9. CRITICAL WARNINGS:**"
            "\n   - Always flag if product contains preservatives not suitable for children"
            "\n   - Warn about carcinogenic combinations (e.g., sodium benzoate + vitamin C = benzene)"
            "\n   - Note hyperactivity triggers for children"
            "\n   - Flag high sodium content for heart/kidney/hypertension patients"
            "\n   - Flag high sugar content for diabetes patients"
            "\n   - Warn about artificial additives for liver disease patients"
            "\n\n**10. NUTRIGRADE CALCULATION (SINGAPORE FOOD GRADING):**"
            "\n   - **MANDATORY**: Assign a NutriGrade (A, B, C, or D) based on the product's nutritional information"
            "\n   - NutriGrade is Singapore's official food grading system based on sugar and saturated fat content"
            "\n   - The grade is determined by the WORST of the two metrics (sugar OR saturated fat)"
            "\n\n   **Sugar Content Grading (per 100ml for beverages, per 100g for food):**"
            "\n   - Grade A: ≤ 1g sugar"
            "\n   - Grade B: > 1g to ≤ 5g sugar"
            "\n   - Grade C: > 5g to ≤ 10g sugar"
            "\n   - Grade D: > 10g sugar"
            "\n\n   **Saturated Fat Content Grading (per 100ml for beverages, per 100g for food):**"
            "\n   - Grade A: ≤ 1.2g saturated fat"
            "\n   - Grade B: > 1.2g to ≤ 2.8g saturated fat"
            "\n   - Grade C: > 2.8g to ≤ 4.0g saturated fat"
            "\n   - Grade D: > 4.0g saturated fat"
            "\n\n   **How to Assign NutriGrade:**"
            "\n   1. Read the Nutrition Facts table from the packaging image"
            "\n   2. Extract sugar content and saturated fat content (per 100g or per 100ml)"
            "\n   3. Determine the grade for sugar using the sugar grading table above"
            "\n   4. Determine the grade for saturated fat using the saturated fat grading table above"
            "\n   5. Assign the WORST grade between the two as the final NutriGrade"
            "\n   6. Example: If sugar = Grade B and saturated fat = Grade D, then NutriGrade = D"
            "\n   7. If nutritional information is not visible or available, assign Grade C as default"
            "\n\nBe thorough, educational, and prioritize consumer safety - especially for vulnerable groups like children, pregnant women, and patients with chronic health conditions (heart disease, kidney disease, diabetes, hypertension, liver disease)."
        ),
    }

    content = [
        {
            "type": "text", 
            "text": "Please analyze the ingredient list from this food packaging image. Extract all ingredients, provide health analysis with ratings, and calculate the NutriGrade (A, B, C, or D) based on the nutritional information visible on the packaging."
        },
        {
            "type": media_type,
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
        # run blocking call in a thread-safe way with Langfuse tracing
        result = await asyncio.to_thread(
            lambda: structured_llm.invoke([system_message, message], config={"callbacks": [get_langfuse_handler()]})
        )
        
        # Flush events to Langfuse
        flush_langfuse()
        
        # Extract parsed data
        parsed: IngredientAnalysis = result["parsed"]
        
        # Convert Pydantic model to dict for AgentResponse
        structured_data = parsed.model_dump()
        
        logger.info("Ingredient scanner agent completed successfully")
        
        return AgentResponse.success_response(structured_data)
            
    except Exception as e:
        logger.error("Ingredient scanner agent model invocation failed", 
                    error=str(e), 
                    exception_type=type(e).__name__)
        return AgentResponse.error_response("Unable to analyze ingredients at this time. Please try again later.")
