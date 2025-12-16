from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from .base import Base


class TokenUsage(Base):
    """Track LLM token usage for analytics and cost monitoring"""
    __tablename__ = "token_usage"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Model and agent information
    model_name = Column(String, nullable=False, index=True)
    agent_type = Column(String, nullable=False, index=True)  # food_agent, nutritionist_agent, etc.
    endpoint = Column(String, nullable=True)  # API endpoint that triggered this
    
    # Token counts
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    
    # Additional metadata
    cache_creation_tokens = Column(Integer, nullable=True, default=0)
    cache_read_tokens = Column(Integer, nullable=True, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="token_usage")
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_user_date', 'user_id', 'created_at'),
        Index('idx_model_date', 'model_name', 'created_at'),
        Index('idx_agent_date', 'agent_type', 'created_at'),
    )
