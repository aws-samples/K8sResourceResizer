"""
Severity level definitions for resource recommendations.

This module defines the severity levels used to indicate:
1. CRITICAL - Major resource misalignment (>50% difference)
2. WARNING - Significant resource misalignment (25-50% difference)
3. OK - Minor resource misalignment (10-25% difference)
4. GOOD - Resources well aligned (<10% difference)
"""

from enum import Enum

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    OK = "OK"
    GOOD = "GOOD" 