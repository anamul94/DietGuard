from sqlalchemy import Column, String, Text, DateTime, Integer, Time, Date, Index
from sqlalchemy.sql import func
from .database import Base

class ReportData(Base):
    __tablename__ = "report_data"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=False)
    data = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

class NutritionData(Base):
    __tablename__ = "nutrition_data"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=False)
    data = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Meal tracking fields
    meal_time = Column(Time, nullable=True)  # Time when meal was consumed (HH:MM:SS)
    meal_date = Column(Date, nullable=True, index=True)  # Date of the meal
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_nutrition_data_user_date', 'user_id', 'meal_date'),
    )