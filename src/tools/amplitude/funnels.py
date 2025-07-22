"""
Amplitude Funnel Analysis API tool
Provides funnel conversion analysis capabilities
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime

from .client import AmplitudeClient


async def get_amplitude_funnel_analysis(
    events: List[str],
    start_date: str,
    end_date: str,
    segments: Optional[List[str]] = None,
    group_by: Optional[str] = None,
    conversion_window_days: int = 7,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get funnel analysis data from Amplitude Dashboard API
    
    Args:
        events: List of event names for funnel steps (in order)
        start_date: Start date in YYYYMMDD format (e.g., "20240101")
        end_date: End date in YYYYMMDD format (e.g., "20240131")
        segments: Optional list of segment names to filter by
        group_by: Optional property to group results by
        conversion_window_days: Number of days for conversion window (default: 7)
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Dictionary containing funnel analysis data including:
        - Conversion rates between steps
        - User counts for each step
        - Drop-off analysis
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
    
    # Validate events
    if len(events) < 2:
        return {
            "error": "Insufficient events",
            "message": "Funnel analysis requires at least 2 events (funnel steps)"
        }
    
    if len(events) > 10:  # Reasonable limit for funnel steps
        return {
            "error": "Too many events",
            "message": "Funnel analysis supports maximum 10 events for performance reasons"
        }
    
    # Validate conversion window
    if conversion_window_days < 1 or conversion_window_days > 365:
        return {
            "error": "Invalid conversion window",
            "message": "Conversion window must be between 1 and 365 days"
        }
    
    client = AmplitudeClient(api_key, secret_key)
    
    try:
        # Convert events to Amplitude funnel format
        event_definitions = []
        for i, event in enumerate(events):
            event_definitions.append({
                "event_type": event,
                "order": i  # Maintain funnel order
            })
        
        # Convert segments to Amplitude format if provided
        segment_definitions = None
        if segments:
            segment_definitions = []
            for segment in segments:
                segment_definitions.append({
                    "prop": segment,
                    "op": "is",
                    "values": ["*"]  # Match all values for this property
                })
        
        # Make the API call
        result = await client.get_funnel_analysis(
            events=event_definitions,
            start_date=start_date,
            end_date=end_date,
            segments=segment_definitions,
            group_by=group_by,
            conversion_window_days=conversion_window_days,
            user_id="mcp_user"  # Default user ID for rate limiting
        )
        
        # Add metadata and enhanced analysis to response
        if "error" not in result:
            result["query_info"] = {
                "start_date": start_date,
                "end_date": end_date,
                "events": events,
                "segments": segments,
                "group_by": group_by,
                "conversion_window_days": conversion_window_days,
                "query_type": "funnel_analysis"
            }
            
            # Add conversion analysis if data is available
            if "data" in result:
                result["conversion_analysis"] = _analyze_funnel_conversions(result["data"], events)
        
        return result
        
    except Exception as e:
        return {
            "error": "Failed to get funnel analysis data",
            "message": str(e)
        }
    finally:
        await client.close()


async def get_amplitude_conversion_summary(
    events: List[str],
    start_date: str,
    end_date: str,
    conversion_window_days: int = 7,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a simplified conversion summary for quick analysis
    
    Args:
        events: List of event names for funnel steps (in order)
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        conversion_window_days: Number of days for conversion window
        api_key: Amplitude API key (optional)
        secret_key: Amplitude secret key (optional)
    
    Returns:
        Dictionary with conversion summary including overall conversion rate and drop-offs
    """
    result = await get_amplitude_funnel_analysis(
        events=events,
        start_date=start_date,
        end_date=end_date,
        segments=None,
        group_by=None,
        conversion_window_days=conversion_window_days,
        api_key=api_key,
        secret_key=secret_key
    )
    
    if "error" in result:
        return result
    
    try:
        if "conversion_analysis" in result:
            return {
                "success": True,
                "conversion_summary": result["conversion_analysis"],
                "query_info": result.get("query_info", {})
            }
        else:
            return {
                "success": True,
                "message": "Funnel data retrieved but conversion analysis not available",
                "raw_result": result
            }
            
    except Exception as e:
        return {
            "error": "Failed to generate conversion summary",
            "message": str(e),
            "raw_result": result
        }


def _analyze_funnel_conversions(funnel_data: Dict[str, Any], events: List[str]) -> Dict[str, Any]:
    """
    Analyze funnel data to extract conversion insights
    
    Args:
        funnel_data: Raw funnel data from Amplitude API
        events: List of event names
    
    Returns:
        Dictionary with conversion analysis
    """
    try:
        analysis = {
            "total_steps": len(events),
            "step_conversions": [],
            "overall_conversion_rate": 0.0,
            "biggest_drop_off": {
                "step": "",
                "drop_off_rate": 0.0
            }
        }
        
        # Extract step data if available
        if "series" in funnel_data:
            series = funnel_data["series"]
            
            step_data = []
            max_drop_off = 0.0
            max_drop_off_step = ""
            
            for i, step_info in enumerate(series):
                if i < len(events):
                    step_name = events[i]
                    user_count = step_info.get("count", 0)
                    
                    # Calculate conversion rate from previous step
                    if i == 0:
                        conversion_rate = 100.0  # First step is 100%
                        drop_off_rate = 0.0
                    else:
                        prev_count = step_data[i-1]["user_count"]
                        if prev_count > 0:
                            conversion_rate = (user_count / prev_count) * 100
                            drop_off_rate = 100 - conversion_rate
                        else:
                            conversion_rate = 0.0
                            drop_off_rate = 100.0
                        
                        # Track biggest drop-off
                        if drop_off_rate > max_drop_off:
                            max_drop_off = drop_off_rate
                            max_drop_off_step = f"{events[i-1]} → {step_name}"
                    
                    step_data.append({
                        "step": i + 1,
                        "event": step_name,
                        "user_count": user_count,
                        "conversion_rate": round(conversion_rate, 2),
                        "drop_off_rate": round(drop_off_rate, 2)
                    })
            
            analysis["step_conversions"] = step_data
            
            # Calculate overall conversion rate
            if step_data and len(step_data) >= 2:
                first_step_count = step_data[0]["user_count"]
                last_step_count = step_data[-1]["user_count"]
                if first_step_count > 0:
                    analysis["overall_conversion_rate"] = round((last_step_count / first_step_count) * 100, 2)
            
            # Set biggest drop-off
            analysis["biggest_drop_off"] = {
                "step": max_drop_off_step,
                "drop_off_rate": round(max_drop_off, 2)
            }
        
        return analysis
        
    except Exception as e:
        return {
            "error": "Failed to analyze conversions",
            "message": str(e)
        }