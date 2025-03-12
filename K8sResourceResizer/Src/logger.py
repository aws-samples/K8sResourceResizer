"""
Logging configuration for the resource optimizer.

This module configures logging with:
1. Console output with colored formatting
2. File output with rotation
3. Different log levels for different destinations

Features:
- Colored console output for better readability
- File rotation to manage log size
- Retention policy for old logs
- Consistent formatting across outputs
"""

from loguru import logger
import sys
import os

# Configure loguru logger
def setup_logger(debug=False):
    """Configure the logger with a specific format and level"""
    logger.remove()  # Remove default handler

    # Get log level from environment variable, default to INFO if not set
    # Override with debug flag if it's True
    console_level = "DEBUG" if debug else os.getenv("DEBUG_LEVEL", "INFO").upper()
    
    # Add console handler with colored output
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=console_level,
        colorize=True
    )
    
    # Add file handler for all logs
    logger.add(
        "logs/k8s_limits_auto_resizer.log",
        rotation="10 MB",
        retention="1 week",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG"  # Always keep DEBUG level for file logging
    )

    # Log initial configuration
    logger.debug("Logger initialized with level={}", console_level)
    return logger 