from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, date, timezone, timedelta
from typing import Optional, Dict, Any, List

from ...infrastructure.database.auth_models import User, TokenUsage
from ...infrastructure.utils.logger import logger


class TokenUsageService:
    """Service for tracking and analyzing LLM token usage"""
    
    @staticmethod
    async def track_token_usage(
        db: AsyncSession,
        user: User,
        model_name: str,
        agent_type: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        endpoint: Optional[str] = None,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0
    ) -> TokenUsage:
        """
        Track token usage for a user's LLM API call.
        
        Args:
            db: Database session
            user: User object
            model_name: Name of the LLM model used
            agent_type: Type of agent (food_agent, nutritionist_agent, etc.)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            total_tokens: Total tokens used
            endpoint: API endpoint that triggered this (optional)
            cache_creation_tokens: Tokens used for cache creation
            cache_read_tokens: Tokens read from cache
            
        Returns:
            TokenUsage record
        """
        token_usage = TokenUsage(
            user_id=user.id,
            model_name=model_name,
            agent_type=agent_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            endpoint=endpoint,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens
        )
        
        db.add(token_usage)
        await db.commit()
        await db.refresh(token_usage)
        
        logger.info(
            "Token usage tracked",
            user_id=str(user.id),
            model=model_name,
            agent=agent_type,
            total_tokens=total_tokens
        )
        
        return token_usage
    
    @staticmethod
    async def get_user_token_stats(
        db: AsyncSession,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get token usage statistics for a specific user.
        
        Args:
            db: Database session
            user_id: User ID
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            
        Returns:
            Dict with user token statistics
        """
        query = select(
            func.sum(TokenUsage.input_tokens).label('total_input'),
            func.sum(TokenUsage.output_tokens).label('total_output'),
            func.sum(TokenUsage.total_tokens).label('total_tokens'),
            func.count(TokenUsage.id).label('api_calls')
        ).where(TokenUsage.user_id == user_id)
        
        if start_date:
            query = query.where(func.date(TokenUsage.created_at) >= start_date)
        if end_date:
            query = query.where(func.date(TokenUsage.created_at) <= end_date)
        
        result = await db.execute(query)
        stats = result.first()
        
        return {
            "user_id": user_id,
            "total_input_tokens": stats.total_input or 0,
            "total_output_tokens": stats.total_output or 0,
            "total_tokens": stats.total_tokens or 0,
            "api_calls": stats.api_calls or 0,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    
    @staticmethod
    async def get_daily_token_stats(
        db: AsyncSession,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get daily token usage statistics.
        
        Args:
            db: Database session
            days: Number of days to look back
            
        Returns:
            List of daily statistics
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = select(
            func.date(TokenUsage.created_at).label('date'),
            func.sum(TokenUsage.input_tokens).label('total_input'),
            func.sum(TokenUsage.output_tokens).label('total_output'),
            func.sum(TokenUsage.total_tokens).label('total_tokens'),
            func.count(TokenUsage.id).label('api_calls')
        ).where(
            TokenUsage.created_at >= start_date
        ).group_by(
            func.date(TokenUsage.created_at)
        ).order_by(
            func.date(TokenUsage.created_at).desc()
        )
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            {
                "date": row.date.isoformat(),
                "total_input_tokens": row.total_input or 0,
                "total_output_tokens": row.total_output or 0,
                "total_tokens": row.total_tokens or 0,
                "api_calls": row.api_calls or 0
            }
            for row in rows
        ]
    
    @staticmethod
    async def get_model_token_stats(
        db: AsyncSession,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Get token usage statistics per model.
        
        Args:
            db: Database session
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            
        Returns:
            List of per-model statistics
        """
        query = select(
            TokenUsage.model_name,
            func.sum(TokenUsage.input_tokens).label('total_input'),
            func.sum(TokenUsage.output_tokens).label('total_output'),
            func.sum(TokenUsage.total_tokens).label('total_tokens'),
            func.count(TokenUsage.id).label('api_calls')
        )
        
        if start_date:
            query = query.where(func.date(TokenUsage.created_at) >= start_date)
        if end_date:
            query = query.where(func.date(TokenUsage.created_at) <= end_date)
        
        query = query.group_by(TokenUsage.model_name).order_by(
            func.sum(TokenUsage.total_tokens).desc()
        )
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            {
                "model_name": row.model_name,
                "total_input_tokens": row.total_input or 0,
                "total_output_tokens": row.total_output or 0,
                "total_tokens": row.total_tokens or 0,
                "api_calls": row.api_calls or 0
            }
            for row in rows
        ]
