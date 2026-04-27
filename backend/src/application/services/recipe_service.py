"""
Service for recipe suggestion and diet profile management.
"""

import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...infrastructure.agents.diet_chart_agent import diet_chart_agent
from ...infrastructure.agents.recipe_suggestion_agent import recipe_suggestion_agent
from ...infrastructure.database.recipe_models import (
    DietProfile,
    GeneratedRecipe,
    WeeklyMealSchedule,
    RecipeTrackingEntry,
)
from ...infrastructure.database.health_models import MealEvent
from ...infrastructure.database.patient_models import PatientPersona
from ...infrastructure.database.auth_models import User
from ...infrastructure.utils.logger import logger
from .token_usage_service import TokenUsageService
from .nutrition_target_service import NutritionTargetService


class RecipeService:
    
    @staticmethod
    async def upload_diet_chart(
        db: AsyncSession,
        user_id: Any,
        file_data: str,
        file_type: str,
        mime_type: str,
        raw_text: Optional[str] = None,
        profile_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload and parse a diet chart document.
        
        Returns the extracted diet restrictions for user confirmation.
        """
        started_at = time.perf_counter()
        logger.info("Diet chart upload started", user_id=str(user_id), file_type=file_type)
        
        agent_response = await diet_chart_agent(
            data=file_data,
            file_type=file_type,
            mime_type=mime_type,
            raw_text=raw_text,
        )
        
        if not agent_response.success:
            raise ValueError(agent_response.error_message)
        
        extraction_data = agent_response.data
        
        metadata = agent_response.metadata if hasattr(agent_response, 'metadata') else {}
        if metadata:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalars().first()
            if user:
                await TokenUsageService.track_token_usage(
                    db=db,
                    user=user,
                    model_name=metadata.get("model_name", "unknown"),
                    agent_type="diet_chart_agent",
                    input_tokens=metadata.get("input_tokens", 0),
                    output_tokens=metadata.get("output_tokens", 0),
                    total_tokens=metadata.get("total_tokens", 0),
                    endpoint="/api/v1/health/diet-profiles/upload",
                )
        
        diet_profile = DietProfile(
            user_id=user_id,
            profile_name=profile_name,
            medical_condition=extraction_data.get("medical_condition"),
            avoid_foods=extraction_data.get("avoid_foods", []),
            limit_foods=extraction_data.get("limit_foods", []),
            allowed_foods=extraction_data.get("allowed_foods", []),
            meal_frequency=extraction_data.get("meal_frequency", 3),
            calorie_limit=extraction_data.get("calorie_limit"),
            salt_limit=extraction_data.get("salt_limit"),
            doctor_notes=extraction_data.get("doctor_notes"),
            extraction_status="pending",
            extracted_raw_text=raw_text,
        )
        db.add(diet_profile)
        await db.commit()
        await db.refresh(diet_profile)
        
        logger.info(
            "Diet profile created from upload",
            user_id=str(user_id),
            profile_id=str(diet_profile.id),
            extraction_confidence=extraction_data.get("extraction_confidence"),
            avoid_count=len(extraction_data.get("avoid_foods", [])),
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        
        return {
            "profile": RecipeService._serialize_profile(diet_profile),
            "extraction_confidence": extraction_data.get("extraction_confidence"),
            "unreadable_sections": extraction_data.get("unreadable_sections", []),
        }
    
    @staticmethod
    async def create_diet_profile_manually(
        db: AsyncSession,
        user_id: Any,
        profile_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a diet profile from manually entered data."""
        
        diet_profile = DietProfile(
            user_id=user_id,
            profile_name=profile_data.get("profile_name"),
            medical_condition=profile_data.get("medical_condition"),
            avoid_foods=profile_data.get("avoid_foods", []),
            limit_foods=profile_data.get("limit_foods", []),
            allowed_foods=profile_data.get("allowed_foods", []),
            meal_frequency=profile_data.get("meal_frequency", 3),
            calorie_limit=profile_data.get("calorie_limit"),
            salt_limit=profile_data.get("salt_limit"),
            doctor_notes=profile_data.get("doctor_notes"),
            extraction_status="confirmed",
            cuisine=profile_data.get("cuisine", []),
            diet_type=profile_data.get("diet_type"),
            allergies=profile_data.get("allergies", []),
            disliked_ingredients=profile_data.get("disliked_ingredients", []),
            cooking_time_pref=profile_data.get("cooking_time_pref"),
            budget_level=profile_data.get("budget_level"),
        )
        db.add(diet_profile)
        await db.commit()
        await db.refresh(diet_profile)
        
        logger.info(
            "Diet profile created manually",
            user_id=str(user_id),
            profile_id=str(diet_profile.id),
        )
        
        return RecipeService._serialize_profile(diet_profile)
    
    @staticmethod
    async def update_diet_profile(
        db: AsyncSession,
        profile_id: Any,
        user_id: Any,
        update_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a diet profile (confirm restrictions or edit preferences)."""
        
        result = await db.execute(
            select(DietProfile).where(
                DietProfile.id == profile_id,
                DietProfile.user_id == user_id,
            )
        )
        profile = result.scalars().first()
        
        if not profile:
            raise ValueError("Diet profile not found")
        
        updatable_fields = [
            "profile_name", "medical_condition", "avoid_foods", "limit_foods",
            "allowed_foods", "meal_frequency", "calorie_limit", "salt_limit",
            "doctor_notes", "extraction_status", "cuisine", "diet_type",
            "allergies", "disliked_ingredients", "cooking_time_pref", "budget_level",
        ]
        
        for field in updatable_fields:
            if field in update_data and update_data[field] is not None:
                setattr(profile, field, update_data[field])
        
        await db.commit()
        await db.refresh(profile)
        
        logger.info(
            "Diet profile updated",
            user_id=str(user_id),
            profile_id=str(profile_id),
        )
        
        return RecipeService._serialize_profile(profile)
    
    @staticmethod
    async def get_diet_profile(
        db: AsyncSession,
        profile_id: Any,
        user_id: Any,
    ) -> Optional[Dict[str, Any]]:
        """Get a specific diet profile."""
        
        result = await db.execute(
            select(DietProfile).where(
                DietProfile.id == profile_id,
                DietProfile.user_id == user_id,
            )
        )
        profile = result.scalars().first()
        
        if not profile:
            return None
        
        return RecipeService._serialize_profile(profile)
    
    @staticmethod
    async def get_active_diet_profile(
        db: AsyncSession,
        user_id: Any,
    ) -> Optional[Dict[str, Any]]:
        """Get the user's active diet profile."""
        
        result = await db.execute(
            select(DietProfile)
            .where(DietProfile.user_id == user_id, DietProfile.is_active.is_(True))
            .order_by(DietProfile.updated_at.desc())
            .limit(1)
        )
        profile = result.scalars().first()
        
        if not profile:
            return None
        
        return RecipeService._serialize_profile(profile)
    
    @staticmethod
    async def get_diet_profiles(
        db: AsyncSession,
        user_id: Any,
    ) -> List[Dict[str, Any]]:
        """Get all diet profiles for a user."""
        
        result = await db.execute(
            select(DietProfile)
            .where(DietProfile.user_id == user_id)
            .order_by(DietProfile.created_at.desc())
        )
        profiles = result.scalars().all()
        
        return [RecipeService._serialize_profile(p) for p in profiles]
    
    @staticmethod
    async def generate_recipe(
        db: AsyncSession,
        user_id: Any,
        diet_profile_id: Any,
        meal_type: str,
        cuisine_override: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a single on-demand recipe."""
        
        profile_result = await db.execute(
            select(DietProfile).where(
                DietProfile.id == diet_profile_id,
                DietProfile.user_id == user_id,
            )
        )
        profile = profile_result.scalars().first()
        
        if not profile:
            raise ValueError("Diet profile not found")
        
        persona_result = await db.execute(
            select(PatientPersona).where(PatientPersona.user_id == user_id)
        )
        persona = persona_result.scalar_one_or_none()
        
        context = await RecipeService._build_recipe_context(
            db=db,
            profile=profile,
            persona=persona,
            meal_type=meal_type,
            cuisine_override=cuisine_override,
        )
        
        agent_response = await recipe_suggestion_agent(context, request_mode="on_demand")
        
        if not agent_response.success:
            raise ValueError(agent_response.error_message)
        
        recipe_data = agent_response.data
        
        metadata = agent_response.metadata if hasattr(agent_response, 'metadata') else {}
        if metadata:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalars().first()
            if user:
                await TokenUsageService.track_token_usage(
                    db=db,
                    user=user,
                    model_name=metadata.get("model_name", "unknown"),
                    agent_type="recipe_suggestion_agent",
                    input_tokens=metadata.get("input_tokens", 0),
                    output_tokens=metadata.get("output_tokens", 0),
                    total_tokens=metadata.get("total_tokens", 0),
                    endpoint="/api/v1/health/recipes/suggest",
                )
        
        recipe = GeneratedRecipe(
            user_id=user_id,
            diet_profile_id=diet_profile_id,
            recipe_name=recipe_data.get("recipe_name"),
            cuisine=recipe_data.get("cuisine"),
            meal_type=recipe_data.get("meal_type"),
            description=recipe_data.get("description"),
            ingredients=recipe_data.get("ingredients", []),
            instructions=recipe_data.get("instructions", []),
            prep_time_minutes=recipe_data.get("prep_time_minutes"),
            cook_time_minutes=recipe_data.get("cook_time_minutes"),
            servings=recipe_data.get("servings", 2),
            nutrition=recipe_data.get("nutrition", {}),
            diet_match_reasons=recipe_data.get("diet_match_reasons", []),
            warnings=recipe_data.get("warnings", []),
            source_type="on_demand",
        )
        db.add(recipe)
        await db.commit()
        await db.refresh(recipe)
        
        logger.info(
            "Recipe generated on-demand",
            user_id=str(user_id),
            recipe_id=str(recipe.id),
            meal_type=meal_type,
        )
        
        return RecipeService._serialize_recipe(recipe)
    
    @staticmethod
    async def generate_weekly_schedule(
        db: AsyncSession,
        user_id: Any,
        diet_profile_id: Any,
        week_start_date: Optional[date] = None,
        cuisine_override: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a weekly meal schedule."""
        
        profile_result = await db.execute(
            select(DietProfile).where(
                DietProfile.id == diet_profile_id,
                DietProfile.user_id == user_id,
            )
        )
        profile = profile_result.scalars().first()
        
        if not profile:
            raise ValueError("Diet profile not found")
        
        persona_result = await db.execute(
            select(PatientPersona).where(PatientPersona.user_id == user_id)
        )
        persona = persona_result.scalar_one_or_none()
        
        if not week_start_date:
            today = date.today()
            days_until_monday = (7 - today.weekday()) % 7
            week_start_date = today if days_until_monday == 0 else today + timedelta(days=days_until_monday)
        
        context = await RecipeService._build_recipe_context(
            db=db,
            profile=profile,
            persona=persona,
            cuisine_override=cuisine_override,
        )
        
        agent_response = await recipe_suggestion_agent(context, request_mode="weekly_schedule")
        
        if not agent_response.success:
            raise ValueError(agent_response.error_message)
        
        schedule_data = agent_response.data
        recipes_data = schedule_data.get("recipes", [])
        
        metadata = agent_response.metadata if hasattr(agent_response, 'metadata') else {}
        if metadata:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalars().first()
            if user:
                await TokenUsageService.track_token_usage(
                    db=db,
                    user=user,
                    model_name=metadata.get("model_name", "unknown"),
                    agent_type="recipe_suggestion_agent",
                    input_tokens=metadata.get("input_tokens", 0),
                    output_tokens=metadata.get("output_tokens", 0),
                    total_tokens=metadata.get("total_tokens", 0),
                    endpoint="/api/v1/health/recipes/generate-schedule",
                )
        
        meal_types = ["breakfast", "lunch", "dinner", "snack"]
        meal_frequency = profile.meal_frequency or 3
        active_meal_types = meal_types[:meal_frequency]
        
        day_schedules = {
            "monday": {},
            "tuesday": {},
            "wednesday": {},
            "thursday": {},
            "friday": {},
            "saturday": {},
            "sunday": {},
        }
        
        saved_recipes = []
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for i, recipe_data in enumerate(recipes_data):
            day_idx = i // meal_frequency
            meal_idx = i % meal_frequency
            
            if day_idx >= 7:
                break
            
            day_name = day_names[day_idx]
            meal_type = active_meal_types[meal_idx] if meal_idx < len(active_meal_types) else "snack"
            
            recipe = GeneratedRecipe(
                user_id=user_id,
                diet_profile_id=diet_profile_id,
                recipe_name=recipe_data.get("recipe_name"),
                cuisine=recipe_data.get("cuisine"),
                meal_type=meal_type,
                description=recipe_data.get("description"),
                ingredients=recipe_data.get("ingredients", []),
                instructions=recipe_data.get("instructions", []),
                prep_time_minutes=recipe_data.get("prep_time_minutes"),
                cook_time_minutes=recipe_data.get("cook_time_minutes"),
                servings=recipe_data.get("servings", 2),
                nutrition=recipe_data.get("nutrition", {}),
                diet_match_reasons=recipe_data.get("diet_match_reasons", []),
                warnings=recipe_data.get("warnings", []),
                source_type="weekly_schedule",
            )
            db.add(recipe)
            await db.flush()
            
            saved_recipes.append(recipe)
            day_schedules[day_name][meal_type] = str(recipe.id)
        
        schedule = WeeklyMealSchedule(
            user_id=user_id,
            diet_profile_id=diet_profile_id,
            week_start_date=week_start_date,
            monday=day_schedules["monday"],
            tuesday=day_schedules["tuesday"],
            wednesday=day_schedules["wednesday"],
            thursday=day_schedules["thursday"],
            friday=day_schedules["friday"],
            saturday=day_schedules["saturday"],
            sunday=day_schedules["sunday"],
            is_active=True,
        )
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
        
        logger.info(
            "Weekly schedule generated",
            user_id=str(user_id),
            schedule_id=str(schedule.id),
            recipe_count=len(saved_recipes),
            week_start=week_start_date.isoformat(),
        )
        
        return RecipeService._serialize_schedule_with_recipes(schedule, saved_recipes)
    
    @staticmethod
    async def get_recipe(
        db: AsyncSession,
        recipe_id: Any,
        user_id: Any,
    ) -> Optional[Dict[str, Any]]:
        """Get a specific recipe by ID."""
        
        result = await db.execute(
            select(GeneratedRecipe).where(
                GeneratedRecipe.id == recipe_id,
                GeneratedRecipe.user_id == user_id,
            )
        )
        recipe = result.scalars().first()
        
        if not recipe:
            return None
        
        return RecipeService._serialize_recipe(recipe)
    
    @staticmethod
    async def get_recipes(
        db: AsyncSession,
        user_id: Any,
        meal_type: Optional[str] = None,
        favorites_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get user's recipes (history/favorites)."""
        
        query = select(GeneratedRecipe).where(GeneratedRecipe.user_id == user_id)
        
        if meal_type:
            query = query.where(GeneratedRecipe.meal_type == meal_type)
        
        if favorites_only:
            query = query.where(GeneratedRecipe.is_favorite.is_(True))
        
        query = query.order_by(GeneratedRecipe.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        recipes = result.scalars().all()
        
        return [RecipeService._serialize_recipe(r) for r in recipes]
    
    @staticmethod
    async def toggle_recipe_favorite(
        db: AsyncSession,
        recipe_id: Any,
        user_id: Any,
    ) -> Dict[str, Any]:
        """Toggle recipe favorite status."""
        
        result = await db.execute(
            select(GeneratedRecipe).where(
                GeneratedRecipe.id == recipe_id,
                GeneratedRecipe.user_id == user_id,
            )
        )
        recipe = result.scalars().first()
        
        if not recipe:
            raise ValueError("Recipe not found")
        
        recipe.is_favorite = not recipe.is_favorite
        await db.commit()
        await db.refresh(recipe)
        
        return RecipeService._serialize_recipe(recipe)
    
    @staticmethod
    async def track_recipe(
        db: AsyncSession,
        user_id: Any,
        recipe_id: Any,
        scheduled_date: Optional[date],
        status: str,
    ) -> Dict[str, Any]:
        """Track a recipe (link to meal tracker)."""
        
        result = await db.execute(
            select(GeneratedRecipe).where(
                GeneratedRecipe.id == recipe_id,
                GeneratedRecipe.user_id == user_id,
            )
        )
        recipe = result.scalars().first()
        
        if not recipe:
            raise ValueError("Recipe not found")
        
        tracking_entry = RecipeTrackingEntry(
            user_id=user_id,
            recipe_id=recipe_id,
            scheduled_date=scheduled_date,
            status=status,
        )
        db.add(tracking_entry)
        
        meal_event = None
        nutrition_added = None
        
        if status in ("cooked", "ate"):
            nutrition = recipe.nutrition or {}
            meal_event = MealEvent(
                user_id=user_id,
                meal_type=recipe.meal_type,
                meal_date=scheduled_date or date.today(),
                meal_time=scheduled_date or date.today(),
                source="recipe",
                status="confirmed",
                total_calories=nutrition.get("calories", 0),
                total_protein_g=nutrition.get("protein_g"),
                total_carbohydrates_g=nutrition.get("carbs_g"),
                total_fat_g=nutrition.get("fat_g"),
                total_fiber_g=nutrition.get("fiber_g"),
            )
            db.add(meal_event)
            await db.flush()
            tracking_entry.meal_event_id = meal_event.id
            nutrition_added = nutrition
        
        await db.commit()
        await db.refresh(tracking_entry)
        
        return {
            "id": str(tracking_entry.id),
            "user_id": str(user_id),
            "recipe_id": str(recipe_id),
            "meal_event_id": str(tracking_entry.meal_event_id) if tracking_entry.meal_event_id else None,
            "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
            "status": tracking_entry.status,
            "created_at": tracking_entry.created_at.isoformat(),
            "recipe_name": recipe.recipe_name,
            "nutrition_added": nutrition_added,
        }
    
    @staticmethod
    async def get_current_schedule(
        db: AsyncSession,
        user_id: Any,
    ) -> Optional[Dict[str, Any]]:
        """Get the user's current active weekly schedule."""
        
        result = await db.execute(
            select(WeeklyMealSchedule)
            .options(selectinload(WeeklyMealSchedule.diet_profile))
            .where(WeeklyMealSchedule.user_id == user_id, WeeklyMealSchedule.is_active.is_(True))
            .order_by(WeeklyMealSchedule.week_start_date.desc())
            .limit(1)
        )
        schedule = result.scalars().first()
        
        if not schedule:
            return None
        
        recipe_ids = []
        day_columns = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in day_columns:
            day_data = getattr(schedule, day, {}) or {}
            for meal_type, rid in day_data.items():
                if rid:
                    recipe_ids.append(rid)
        
        recipes_result = await db.execute(
            select(GeneratedRecipe).where(GeneratedRecipe.id.in_(recipe_ids))
        )
        recipes = {str(r.id): r for r in recipes_result.scalars().all()}
        
        return RecipeService._serialize_schedule_with_recipes_dict(schedule, recipes)
    
    @staticmethod
    async def _build_recipe_context(
        db: AsyncSession,
        profile: DietProfile,
        persona: Optional[PatientPersona],
        meal_type: Optional[str] = None,
        cuisine_override: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build context dictionary for recipe generation agent.
        
        Fetches calorie target from:
        1. Diet profile's calorie_limit (from doctor's chart) - highest priority
        2. User's NutritionTarget (calculated from their health profile)
        3. Default fallback (2000 kcal)
        """
        
        cuisines = cuisine_override if cuisine_override else (profile.cuisine or ["Indian"])
        
        calorie_target = profile.calorie_limit
        if not calorie_target:
            nutrition_target = await NutritionTargetService.get_current_target(db, profile.user_id)
            if nutrition_target:
                calorie_target = nutrition_target.get("calories_kcal")
        
        if not calorie_target:
            calorie_target = 2000
        
        meal_frequency = profile.meal_frequency or 3
        calories_per_meal = calorie_target / meal_frequency
        
        meal_calorie_targets = {
            "breakfast": round(calories_per_meal * 0.9),
            "lunch": round(calories_per_meal * 1.1),
            "dinner": round(calories_per_meal * 0.9),
            "snack": round(calories_per_meal * 0.5),
        }
        
        return {
            "medical_condition": profile.medical_condition,
            "avoid_foods": profile.avoid_foods or [],
            "limit_foods": profile.limit_foods or [],
            "allowed_foods": profile.allowed_foods or [],
            "meal_frequency": meal_frequency,
            "doctor_notes": profile.doctor_notes,
            "cuisine": cuisines,
            "diet_type": profile.diet_type or "non_vegetarian",
            "allergies": profile.allergies or [],
            "disliked_ingredients": profile.disliked_ingredients or [],
            "cooking_time_pref": profile.cooking_time_pref or "30_min",
            "calorie_target": calorie_target,
            "meal_type": meal_type,
            "meal_calorie_target": meal_calorie_targets.get(meal_type, round(calories_per_meal)),
        }
    
    @staticmethod
    def _serialize_profile(profile: DietProfile) -> Dict[str, Any]:
        """Serialize a diet profile to dict."""
        return {
            "id": str(profile.id),
            "user_id": str(profile.user_id),
            "profile_name": profile.profile_name,
            "source_file_url": profile.source_file_url,
            "medical_condition": profile.medical_condition,
            "avoid_foods": profile.avoid_foods or [],
            "limit_foods": profile.limit_foods or [],
            "allowed_foods": profile.allowed_foods or [],
            "meal_frequency": profile.meal_frequency,
            "calorie_limit": profile.calorie_limit,
            "salt_limit": profile.salt_limit,
            "doctor_notes": profile.doctor_notes,
            "extraction_status": profile.extraction_status,
            "extracted_raw_text": profile.extracted_raw_text,
            "cuisine": profile.cuisine or [],
            "diet_type": profile.diet_type,
            "allergies": profile.allergies or [],
            "disliked_ingredients": profile.disliked_ingredients or [],
            "cooking_time_pref": profile.cooking_time_pref,
            "budget_level": profile.budget_level,
            "is_active": profile.is_active,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat(),
        }
    
    @staticmethod
    def _serialize_recipe(recipe: GeneratedRecipe) -> Dict[str, Any]:
        """Serialize a recipe to dict."""
        return {
            "id": str(recipe.id),
            "user_id": str(recipe.user_id),
            "diet_profile_id": str(recipe.diet_profile_id) if recipe.diet_profile_id else None,
            "recipe_name": recipe.recipe_name,
            "cuisine": recipe.cuisine,
            "meal_type": recipe.meal_type,
            "description": recipe.description,
            "ingredients": recipe.ingredients or [],
            "instructions": recipe.instructions or [],
            "prep_time_minutes": recipe.prep_time_minutes,
            "cook_time_minutes": recipe.cook_time_minutes,
            "servings": recipe.servings,
            "nutrition": recipe.nutrition or {},
            "diet_match_reasons": recipe.diet_match_reasons or [],
            "warnings": recipe.warnings or [],
            "is_favorite": recipe.is_favorite,
            "source_type": recipe.source_type,
            "created_at": recipe.created_at.isoformat(),
        }
    
    @staticmethod
    def _serialize_schedule_with_recipes(
        schedule: WeeklyMealSchedule,
        recipes: List[GeneratedRecipe],
    ) -> Dict[str, Any]:
        """Serialize a schedule with embedded recipe objects."""
        recipes_by_id = {str(r.id): RecipeService._serialize_recipe(r) for r in recipes}
        
        days = {}
        day_columns = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for day in day_columns:
            day_data = getattr(schedule, day, {}) or {}
            days[day] = {
                meal_type: recipes_by_id.get(str(recipe_id))
                for meal_type, recipe_id in day_data.items()
            }
        
        return {
            "id": str(schedule.id),
            "user_id": str(schedule.user_id),
            "diet_profile_id": str(schedule.diet_profile_id) if schedule.diet_profile_id else None,
            "week_start_date": schedule.week_start_date.isoformat(),
            "compliance_score": schedule.compliance_score,
            "is_active": schedule.is_active,
            "created_at": schedule.created_at.isoformat(),
            "days": days,
        }
    
    @staticmethod
    def _serialize_schedule_with_recipes_dict(
        schedule: WeeklyMealSchedule,
        recipes: Dict[str, GeneratedRecipe],
    ) -> Dict[str, Any]:
        """Serialize a schedule with pre-fetched recipes dict."""
        days = {}
        day_columns = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for day in day_columns:
            day_data = getattr(schedule, day, {}) or {}
            days[day] = {}
            for meal_type, recipe_id in day_data.items():
                recipe = recipes.get(str(recipe_id))
                if recipe:
                    days[day][meal_type] = RecipeService._serialize_recipe(recipe)
        
        return {
            "id": str(schedule.id),
            "user_id": str(schedule.user_id),
            "diet_profile_id": str(schedule.diet_profile_id) if schedule.diet_profile_id else None,
            "week_start_date": schedule.week_start_date.isoformat(),
            "compliance_score": schedule.compliance_score,
            "is_active": schedule.is_active,
            "created_at": schedule.created_at.isoformat(),
            "days": days,
        }
