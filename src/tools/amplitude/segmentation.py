"""
Amplitude Event Segmentation API tool
Provides event segmentation analysis capabilities
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime

from .client import AmplitudeClient


async def get_amplitude_event_segmentation(
    start_date: str,
    end_date: str,
    events: List[str],
    segments: Optional[List[str]] = None,
    group_by: Optional[str] = None,
    interval: str = "daily",
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get event segmentation data from Amplitude Dashboard API
    
    Args:
        start_date: Start date in YYYYMMDD format (e.g., "20240101")
        end_date: End date in YYYYMMDD format (e.g., "20240131")
        events: List of event names to analyze (up to 2 events)
        segments: Optional list of segment names to filter by
        group_by: Optional property to group results by
        interval: Interval type - "daily", "weekly", or "monthly"
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Dictionary containing event segmentation data including:
        - Event counts over time
        - Unique user counts
        - Total values
        - Segmented breakdowns (if segments provided)
    """
    # Get API credentials
    api_key = api_key or os.getenv("AMPLITUDE_API_KEY")
    secret_key = secret_key or os.getenv("AMPLITUDE_SECRET_KEY")
    
    if not api_key or not secret_key:
        return {
            "error": "Missing Amplitude API credentials",
            "message": "Please provide api_key and secret_key, or set AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY environment variables"
        }
    
    # Validate date format
    try:
        datetime.strptime(start_date, "%Y%m%d")
        datetime.strptime(end_date, "%Y%m%d")
    except ValueError:
        return {
            "error": "Invalid date format",
            "message": "Dates must be in YYYYMMDD format (e.g., '20240101')"
        }
    
    # Validate events limit for segmentation
    if len(events) > 2:
        return {
            "error": "Too many events",
            "message": "Amplitude Event Segmentation API supports maximum 2 events"
        }
    
    if not events:
        return {
            "error": "No events provided",
            "message": "At least one event must be specified"
        }
    
    # Convert interval to Amplitude format
    interval_map = {
        "daily": 1,
        "weekly": 7,
        "monthly": 30
    }
    
    if interval not in interval_map:
        return {
            "error": "Invalid interval",
            "message": "Interval must be 'daily', 'weekly', or 'monthly'"
        }
    
    interval_value = interval_map[interval]
    
    client = AmplitudeClient(api_key, secret_key)
    
    try:
        # Convert events to Amplitude format
        event_definitions = []
        for event in events:
            event_definitions.append({
                "event_type": event
            })
        
        # Convert segments to Amplitude format if provided
        segment_definitions = None
        if segments:
            segment_definitions = []
            for segment in segments:
                # Basic segment definition - can be extended for more complex segments
                segment_definitions.append({
                    "prop": segment,
                    "op": "is",
                    "values": ["*"]  # Match all values for this property
                })
        
        # Make the API call
        result = await client.get_event_segmentation(
            start_date=start_date,
            end_date=end_date,
            events=event_definitions,
            segments=segment_definitions,
            group_by=group_by,
            interval=interval_value,
            user_id="mcp_user"  # Default user ID for rate limiting
        )
        
        # Add metadata to response
        if "error" not in result:
            result["query_info"] = {
                "start_date": start_date,
                "end_date": end_date,
                "events": events,
                "segments": segments,
                "group_by": group_by,
                "interval": interval,
                "query_type": "event_segmentation"
            }
        
        return result
        
    except Exception as e:
        return {
            "error": "Failed to get event segmentation data",
            "message": str(e)
        }
    finally:
        await client.close()


async def get_amplitude_event_totals(
    start_date: str,
    end_date: str,
    events: List[str],
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get event totals for a quick summary (wrapper around event segmentation)
    
    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format  
        events: List of event names to get totals for
        api_key: Amplitude API key (optional)
        secret_key: Amplitude secret key (optional)
    
    Returns:
        Dictionary with event totals and unique user counts
    """
    result = await get_amplitude_event_segmentation(
        start_date=start_date,
        end_date=end_date,
        events=events,
        segments=None,
        group_by=None,
        interval="daily",
        api_key=api_key,
        secret_key=secret_key
    )
    
    if "error" in result:
        return result
    
    # Extract totals from the segmentation result
    try:
        totals = {}
        if "data" in result:
            series = result["data"].get("series", [])
            for i, event in enumerate(events):
                if i < len(series):
                    event_data = series[i]
                    totals[event] = {
                        "total_events": sum(event_data.get("values", [])),
                        "unique_users": sum(event_data.get("unique_users", [])) if "unique_users" in event_data else None
                    }
        
        return {
            "success": True,
            "totals": totals,
            "query_info": result.get("query_info", {})
        }
        
    except Exception as e:
        return {
            "error": "Failed to extract totals",
            "message": str(e),
            "raw_result": result
        }