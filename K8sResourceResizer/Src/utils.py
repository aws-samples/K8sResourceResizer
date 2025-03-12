"""
Utility functions and decorators for the resource optimizer.

This module provides common utilities:
1. Directory creation and validation
2. Global exception handling decorator
3. Logging setup helpers
4. Time duration parsing

The exception handler ensures consistent error handling across all functions
by logging errors with full context and re-raising them for proper handling.
"""

import os
from logger import logger
from functools import wraps
import re

def ensure_directory_exists(path):
    """
    Ensure that the directory exists, creating it if necessary.

    Args:
        path (str): Directory path.
    """
    if not os.path.exists(path):
        logger.info(f"Creating directory: {path}")
        os.makedirs(path)

def parse_duration(duration_str: str) -> int:
    """
    Parse a human-readable duration string into hours.
    
    Supports formats:
    - Hours: 24h, 12h
    - Days: 7d, 14d
    - Weeks: 1w, 2w
    - Years: 1yr, 2yr
    
    Args:
        duration_str (str): Duration string (e.g., "24h", "7d", "8w", "1yr")
        
    Returns:
        int: Number of hours
        
    Raises:
        ValueError: If the format is invalid
    """
    if not duration_str:
        return 24  # Default to 24 hours
        
    pattern = re.compile(r'^(\d+)(h|d|w|yr)$')
    match = pattern.match(duration_str.lower())
    
    if not match:
        raise ValueError(
            "Invalid duration format. Use: "
            "##h for hours, ##d for days, ##w for weeks, ##yr for years"
        )
    
    value, unit = match.groups()
    value = int(value)
    
    # Convert to hours
    multipliers = {
        'h': 1,
        'd': 24,
        'w': 24 * 7,
        'yr': 24 * 365
    }
    
    return value * multipliers[unit]

def handle_exceptions(func):
    """
    A decorator that wraps functions to handle all exceptions consistently.
    Logs the error and re-raises it.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Get the function name for better error messages
            func_name = func.__name__
            # Log with full context
            logger.error(f"Error in {func_name}: {str(e)}", exc_info=True)
            # Re-raise the exception
            raise
    return wrapper
