"""
San Francisco Time API Tool
Provides current time and timezone information for San Francisco
"""

from datetime import datetime
import pytz
from typing import Dict, Any


async def get_san_francisco_time() -> Dict[str, Any]:
    """
    Get current time in San Francisco timezone
    
    Returns:
        Dict containing current time, timezone info, and formatted strings
    """
    try:
        # San Francisco coordinates
        latitude = 37.7749
        longitude = -122.4194
        
        # Get San Francisco timezone
        sf_tz = pytz.timezone('America/Los_Angeles')
        utc_now = datetime.now(pytz.UTC)
        sf_time = utc_now.astimezone(sf_tz)
        
        return {
            "success": True,
            "location": "San Francisco, CA",
            "coordinates": {
                "latitude": latitude,
                "longitude": longitude
            },
            "timezone": {
                "name": sf_tz.zone,
                "abbreviation": sf_time.strftime('%Z'),
                "utc_offset": sf_time.strftime('%z')
            },
            "current_time": {
                "iso_format": sf_time.isoformat(),
                "formatted": sf_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                "unix_timestamp": int(sf_time.timestamp())
            },
            "utc_time": {
                "iso_format": utc_now.isoformat(),
                "formatted": utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to get San Francisco time"
        }