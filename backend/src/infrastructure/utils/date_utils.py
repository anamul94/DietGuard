"""
Date utility functions for the application.
"""

from datetime import datetime, timezone
from typing import Optional


def calculate_age(date_of_birth: Optional[datetime]) -> Optional[int]:
    """
    Calculate age from date of birth.
    
    Args:
        date_of_birth: User's date of birth (timezone-aware datetime)
        
    Returns:
        Age in years, or None if date_of_birth is None
    """
    if not date_of_birth:
        return None
    
    today = datetime.now(timezone.utc)
    age = today.year - date_of_birth.year
    
    # Adjust if birthday hasn't occurred yet this year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    
    return age


def validate_date_of_birth(date_of_birth: datetime) -> bool:
    """
    Validate that date of birth is valid (not in the future).
    
    Args:
        date_of_birth: Date of birth to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not date_of_birth:
        return False
    
    # Check if date is in the future
    if date_of_birth > datetime.now(timezone.utc):
        return False
    
    return True
