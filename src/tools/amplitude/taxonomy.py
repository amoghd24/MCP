"""
Amplitude Events List API tool
Provides simple event discovery capabilities using the events/list endpoint
"""

import os
from typing import Dict, Any, Optional, List

from .client import AmplitudeClient


async def get_amplitude_events_list(
    include_totals: bool = True,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a simple list of all visible events with current week's metrics
    
    Args:
        include_totals: Whether to include current week's totals (always True for this endpoint)
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Dictionary containing:
        - List of all visible event names
        - Current week's totals for each event
        - Event status (active/inactive, hidden, etc.)
    """
    # Get API credentials
    api_key = api_key or os.getenv("AMPLITUDE_API_KEY")
    secret_key = secret_key or os.getenv("AMPLITUDE_SECRET_KEY")
    
    if not api_key or not secret_key:
        return {
            "error": "Missing Amplitude API credentials",
            "message": "Please provide api_key and secret_key, or set AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY environment variables"
        }
    
    client = AmplitudeClient(api_key, secret_key)
    
    try:
        # Make the simple Events List API call
        result = await client.get_events_list(user_id="mcp_user")
        
        # Process and enhance the response
        if "error" not in result:
            processed_result = _process_events_list_response(result)
            return processed_result
        
        return result
        
    except Exception as e:
        return {
            "error": "Failed to get events list from Amplitude",
            "message": str(e)
        }
    finally:
        await client.close()


async def get_amplitude_event_details(
    event_name: str,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get details for a specific event from the events list
    
    Args:
        event_name: Name of the event to get details for
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Detailed event information including current week's metrics
    """
    # Get all events first
    all_events = await get_amplitude_events_list(api_key=api_key, secret_key=secret_key)
    
    if "error" in all_events:
        return all_events
    
    # Find the specific event
    for event in all_events.get("events", []):
        if event.get("name", "").lower() == event_name.lower():
            return {
                "success": True,
                "event": event,
                "query_info": {
                    "event_name": event_name,
                    "query_type": "event_details"
                }
            }
    
    return {
        "error": "Event not found",
        "message": f"Event '{event_name}' not found in visible events",
        "suggestion": "Use get_amplitude_events_list() to see all available events"
    }


def _process_events_list_response(raw_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process the events/list API response into a clean format
    
    Args:
        raw_response: Raw response from Amplitude Events List API
        
    Returns:
        Processed response with clean event information
    """
    try:
        processed = {
            "success": True,
            "events": [],
            "summary": {
                "total_events": 0,
                "active_events": 0,
                "inactive_events": 0,
                "hidden_events": 0,
                "total_volume_this_week": 0
            },
            "query_info": {
                "query_type": "events_list",
                "data_period": "current_week"
            }
        }
        
        # Handle the events/list response format
        events_data = raw_response.get("data", [])
        
        for event in events_data:
            if isinstance(event, dict):
                event_info = {
                    "name": event.get("value", event.get("display", "Unknown")),
                    "display_name": event.get("display", event.get("value", "Unknown")),
                    "totals_this_week": event.get("totals", 0),
                    "is_active": not event.get("non_active", False),
                    "is_deleted": event.get("deleted", False),
                    "is_hidden": event.get("hidden", False),
                    "is_flow_hidden": event.get("flow_hidden", False)
                }
                
                processed["events"].append(event_info)
                processed["summary"]["total_events"] += 1
                processed["summary"]["total_volume_this_week"] += event_info["totals_this_week"]
                
                if event_info["is_active"] and not event_info["is_deleted"]:
                    processed["summary"]["active_events"] += 1
                else:
                    processed["summary"]["inactive_events"] += 1
                    
                if event_info["is_hidden"] or event_info["is_flow_hidden"]:
                    processed["summary"]["hidden_events"] += 1
        
        # Create simple event names list for easy access
        processed["event_names"] = [event["name"] for event in processed["events"]]
        
        # Add insights based on current week's data
        processed["insights"] = _generate_events_insights(processed)
        
        return processed
        
    except Exception as e:
        return {
            "error": "Failed to process events list response",
            "message": str(e),
            "raw_response": raw_response
        }


def _generate_events_insights(processed_data: Dict[str, Any]) -> List[str]:
    """
    Generate insights based on events list data
    
    Args:
        processed_data: Processed events data
        
    Returns:
        List of insight strings
    """
    insights = []
    
    try:
        summary = processed_data.get("summary", {})
        events = processed_data.get("events", [])
        
        total_events = summary.get("total_events", 0)
        active_events = summary.get("active_events", 0)
        total_volume = summary.get("total_volume_this_week", 0)
        
        if total_events == 0:
            insights.append("No events found - check your API credentials and project access")
            return insights
        
        insights.append(f"Found {active_events} active events with {total_volume:,} total occurrences this week")
        
        # Find top events by volume
        if events:
            top_events = sorted(events, key=lambda x: x.get("totals_this_week", 0), reverse=True)[:3]
            if top_events[0].get("totals_this_week", 0) > 0:
                top_event_names = [f"{e['name']} ({e['totals_this_week']:,})" for e in top_events if e.get("totals_this_week", 0) > 0]
                if top_event_names:
                    insights.append(f"Top events this week: {', '.join(top_event_names)}")
        
        # Check for inactive events
        inactive_count = summary.get("inactive_events", 0)
        if inactive_count > 0:
            insights.append(f"{inactive_count} inactive events detected - consider cleanup")
        
        insights.append("Events ready for segmentation, funnel, and retention analysis")
        
    except Exception:
        insights.append("Events retrieved successfully - ready for analysis")
    
    return insights