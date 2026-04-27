"""
Recipe suggestion and diet profile models.

These tables support the AI-powered recipe suggestion feature that generates
personalized recipes based on doctor-prescribed diet restrictions.
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class DietProfile(Base):
    """
    User's diet profile extracted from doctor's diet chart/instructions.
    
    Stores both extracted restrictions and user preferences for recipe generation.
    Also stores detailed meal plans and nutrition targets if specified in the document.
    """
    __tablename__ = "diet_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_name = Column(String(255), nullable=True)
    source_file_url = Column(String(500), nullable=True)
    
    medical_condition = Column(String(100), nullable=True)
    avoid_foods = Column(JSONB, nullable=False, default=list)
    limit_foods = Column(JSONB, nullable=False, default=list)
    allowed_foods = Column(JSONB, nullable=False, default=list)
    meal_frequency = Column(Integer, nullable=True, default=3)
    calorie_limit = Column(Integer, nullable=True)
    salt_limit = Column(String(50), nullable=True)
    doctor_notes = Column(Text, nullable=True)
    extraction_status = Column(String(30), nullable=False, default="pending")
    extracted_raw_text = Column(Text, nullable=True)
    
    nutrition_targets = Column(JSONB, nullable=True, default=dict)
    meal_plans = Column(JSONB, nullable=False, default=list)
    
    cuisine = Column(JSONB, nullable=False, default=list)
    diet_type = Column(String(30), nullable=True)
    allergies = Column(JSONB, nullable=False, default=list)
    disliked_ingredients = Column(JSONB, nullable=False, default=list)
    cooking_time_pref = Column(String(30), nullable=True)
    budget_level = Column(String(20), nullable=True)
    
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    recipes = relationship("GeneratedRecipe", back_populates="diet_profile", cascade="all, delete-orphan")
    schedules = relationship("WeeklyMealSchedule", back_populates="diet_profile", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_diet_profiles_user_active", "user_id", "is_active"),
    )


class GeneratedRecipe(Base):
    """
    AI-generated recipe aligned with user's diet restrictions.
    
    Includes full recipe details with AI-estimated nutrition.
    """
    __tablename__ = "generated_recipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    diet_profile_id = Column(UUID(as_uuid=True), ForeignKey("diet_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    
    recipe_name = Column(String(255), nullable=False)
    cuisine = Column(String(50), nullable=True)
    meal_type = Column(String(30), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    ingredients = Column(JSONB, nullable=False, default=list)
    instructions = Column(JSONB, nullable=False, default=list)
    
    prep_time_minutes = Column(Integer, nullable=True)
    cook_time_minutes = Column(Integer, nullable=True)
    servings = Column(Integer, nullable=False, default=2)
    
    nutrition = Column(JSONB, nullable=False, default=dict)
    
    diet_match_reasons = Column(JSONB, nullable=False, default=list)
    warnings = Column(JSONB, nullable=False, default=list)
    
    is_favorite = Column(Boolean, nullable=False, default=False, index=True)
    source_type = Column(String(30), nullable=False, default="on_demand")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    diet_profile = relationship("DietProfile", back_populates="recipes")
    tracking_entries = relationship("RecipeTrackingEntry", back_populates="recipe", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_generated_recipes_user_meal_type", "user_id", "meal_type"),
        Index("idx_generated_recipes_user_favorite", "user_id", "is_favorite"),
    )


class WeeklyMealSchedule(Base):
    """
    Weekly meal schedule generated from diet profile.
    
    Each day column stores a mapping of meal_type -> recipe_id.
    """
    __tablename__ = "weekly_meal_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    diet_profile_id = Column(UUID(as_uuid=True), ForeignKey("diet_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    
    week_start_date = Column(Date, nullable=False, index=True)
    
    monday = Column(JSONB, nullable=False, default=dict)
    tuesday = Column(JSONB, nullable=False, default=dict)
    wednesday = Column(JSONB, nullable=False, default=dict)
    thursday = Column(JSONB, nullable=False, default=dict)
    friday = Column(JSONB, nullable=False, default=dict)
    saturday = Column(JSONB, nullable=False, default=dict)
    sunday = Column(JSONB, nullable=False, default=dict)
    
    compliance_score = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    diet_profile = relationship("DietProfile", back_populates="schedules")

    __table_args__ = (
        Index("idx_weekly_meal_schedules_user_date", "user_id", "week_start_date"),
        Index("idx_weekly_meal_schedules_user_active", "user_id", "is_active"),
    )


class RecipeTrackingEntry(Base):
    """
    Links generated recipes to the existing meal tracking system.
    
    Tracks whether user cooked, ate, skipped, or replaced a scheduled recipe.
    """
    __tablename__ = "recipe_tracking_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe_id = Column(UUID(as_uuid=True), ForeignKey("generated_recipes.id", ondelete="CASCADE"), nullable=False, index=True)
    meal_event_id = Column(UUID(as_uuid=True), ForeignKey("meal_events.id", ondelete="SET NULL"), nullable=True, index=True)
    
    scheduled_date = Column(Date, nullable=True, index=True)
    status = Column(String(20), nullable=False, default="scheduled")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    recipe = relationship("GeneratedRecipe", back_populates="tracking_entries")

    __table_args__ = (
        Index("idx_recipe_tracking_user_date", "user_id", "scheduled_date"),
    )
