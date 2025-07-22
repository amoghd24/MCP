"""
Amplitude Taxonomy API tool
Provides event discovery and schema management capabilities
"""

import os
from typing import Dict, Any, Optional, List

from .client import AmplitudeClient


async def get_amplitude_events_list(
    include_deleted: bool = False,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a complete list of all event types in the Amplitude project
    
    Args:
        include_deleted: Whether to include deleted/inactive events (default: False)
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Dictionary containing:
        - List of all event names
        - Event metadata (descriptions, categories, etc.)
        - Active/inactive status
        - Event properties information
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
        # Make the Taxonomy API call
        result = await client.get_all_events(
            include_deleted=include_deleted,
            user_id="mcp_user"
        )
        
        # Process and enhance the response
        if "error" not in result:
            # Extract event information and create a clean response
            processed_result = _process_events_response(result, include_deleted)
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
    Get detailed information about a specific event
    
    Args:
        event_name: Name of the event to get details for
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Detailed event information including properties, description, category
    """
    # Get API credentials
    api_key = api_key or os.getenv("AMPLITUDE_API_KEY")
    secret_key = secret_key or os.getenv("AMPLITUDE_SECRET_KEY")
    
    if not api_key or not secret_key:
        return {
            "error": "Missing Amplitude API credentials",
            "message": "Please provide api_key and secret_key, or set AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY environment variables"
        }
    
    if not event_name:
        return {
            "error": "Missing event name",
            "message": "Please provide an event name to get details for"
        }
    
    client = AmplitudeClient(api_key, secret_key)
    
    try:
        # Make API call to get specific event details
        # Note: This would use GET /api/2/taxonomy/event/{event_name}
        # For now, we'll get all events and filter to the specific one
        result = await client.get_all_events(
            include_deleted=True,  # Include all events for detailed search
            user_id="mcp_user"
        )
        
        if "error" in result:
            return result
        
        # Find the specific event in the results
        event_details = _find_event_in_response(result, event_name)
        if event_details:
            return {
                "success": True,
                "event": event_details,
                "query_info": {
                    "event_name": event_name,
                    "query_type": "event_details"
                }
            }
        else:
            return {
                "error": "Event not found",
                "message": f"Event '{event_name}' not found in Amplitude project",
                "suggestion": "Use get_amplitude_events_list() to see all available events"
            }
        
    except Exception as e:
        return {
            "error": "Failed to get event details from Amplitude",
            "message": str(e)
        }
    finally:
        await client.close()


def _process_events_response(raw_response: Dict[str, Any], include_deleted: bool) -> Dict[str, Any]:
    """
    Process the raw Taxonomy API response into a clean, user-friendly format
    
    Args:
        raw_response: Raw response from Amplitude Taxonomy API
        include_deleted: Whether deleted events were included
        
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
                "deleted_events": 0,
                "categorized_events": 0
            },
            "categories": set(),
            "query_info": {
                "include_deleted": include_deleted,
                "query_type": "events_list"
            }
        }
        
        # Handle different possible response formats from Amplitude API
        events_data = []
        
        if isinstance(raw_response, dict):
            # Check for common response formats
            if "data" in raw_response:
                events_data = raw_response["data"]
            elif "events" in raw_response:
                events_data = raw_response["events"]
            elif isinstance(raw_response.get("taxonomy", {}), list):
                events_data = raw_response["taxonomy"]
            else:
                # If it's a direct list or other format
                events_data = raw_response if isinstance(raw_response, list) else [raw_response]
        
        # Process each event
        for event in events_data:
            if isinstance(event, dict):
                event_info = {
                    "name": event.get("event_type", event.get("name", "Unknown")),
                    "description": event.get("description", ""),
                    "category": event.get("category", "Uncategorized"),
                    "is_active": event.get("is_active", True),
                    "is_deleted": event.get("is_deleted", False),
                    "properties_count": len(event.get("properties", [])),
                    "tags": event.get("tags", [])
                }
                
                processed["events"].append(event_info)
                processed["summary"]["total_events"] += 1
                
                if event_info["is_active"] and not event_info["is_deleted"]:
                    processed["summary"]["active_events"] += 1
                
                if event_info["is_deleted"]:
                    processed["summary"]["deleted_events"] += 1
                
                if event_info["category"] and event_info["category"] != "Uncategorized":
                    processed["summary"]["categorized_events"] += 1
                    processed["categories"].add(event_info["category"])
            
            elif isinstance(event, str):
                # Simple string format - just event names
                event_info = {
                    "name": event,
                    "description": "",
                    "category": "Uncategorized",
                    "is_active": True,
                    "is_deleted": False,
                    "properties_count": 0,
                    "tags": []
                }
                
                processed["events"].append(event_info)
                processed["summary"]["total_events"] += 1
                processed["summary"]["active_events"] += 1
        
        # Convert categories set to list
        processed["categories"] = list(processed["categories"])
        
        # Create a simple event names list for easy access
        processed["event_names"] = [event["name"] for event in processed["events"]]
        
        # Add recommendations
        processed["recommendations"] = _generate_event_recommendations(processed)
        
        return processed
        
    except Exception as e:
        return {
            "error": "Failed to process events response",
            "message": str(e),
            "raw_response": raw_response
        }


def _find_event_in_response(raw_response: Dict[str, Any], event_name: str) -> Optional[Dict[str, Any]]:
    """
    Find a specific event in the taxonomy response
    
    Args:
        raw_response: Raw response from Taxonomy API
        event_name: Name of event to find
        
    Returns:
        Event details if found, None otherwise
    """
    try:
        # Process the response to find the event
        processed = _process_events_response(raw_response, True)
        
        if "events" in processed:
            for event in processed["events"]:
                if event.get("name", "").lower() == event_name.lower():
                    return event
        
        return None
        
    except Exception:
        return None


def _generate_event_recommendations(processed_data: Dict[str, Any]) -> List[str]:
    """
    Generate recommendations based on the events analysis
    
    Args:
        processed_data: Processed events data
        
    Returns:
        List of recommendation strings
    """
    recommendations = []
    
    try:
        summary = processed_data.get("summary", {})
        total_events = summary.get("total_events", 0)
        active_events = summary.get("active_events", 0)
        categorized_events = summary.get("categorized_events", 0)
        
        if total_events == 0:
            recommendations.append("No events found - check your API credentials and project access")
        elif active_events == 0:
            recommendations.append("No active events found - check if events are being tracked properly")
        else:
            recommendations.append(f"Found {active_events} active events ready for analysis")
            
            if categorized_events < active_events * 0.5:
                recommendations.append("Consider categorizing your events for better organization")
            
            if total_events > 50:
                recommendations.append("Large number of events - consider using categories and filters for analysis")
            
            # Suggest common analytics workflows
            recommendations.append("Use these events with funnel analysis, retention analysis, or event segmentation tools")
    
    except Exception:
        recommendations.append("Events retrieved successfully - ready for analysis")
    
    return recommendations