"""
Amplitude Funnel Analysis API tool
Provides funnel conversion analysis with step-by-step drop-off rates
"""

from typing import Dict, Any, Optional, List, Union

from .client import AmplitudeClient
from .utils import (
    get_api_credentials,
    validate_date_format,
    validate_events_list,
    validate_funnel_mode,
    validate_user_segment,
    validate_funnel_interval,
    validate_funnel_conversion_window,
    create_error_response,
    add_query_metadata
)


async def get_amplitude_funnel(
    events: List[Union[str, Dict[str, str]]],
    start_date: str,
    end_date: str,
    mode: str = "ordered",
    user_segment: str = "active",
    conversion_window_days: int = 7,
    interval: int = 1,
    group_by: Optional[str] = None,
    segments: Optional[List[Dict[str, Any]]] = None,
    limit: int = 100,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get funnel analysis data from Amplitude with step-by-step conversion rates
    
    Args:
        events: List of funnel step events. Can be event names (strings) or event dicts with 'event_type' key
        start_date: Start date in YYYYMMDD format (e.g., "20240101")
        end_date: End date in YYYYMMDD format (e.g., "20240131")
        mode: Funnel mode - "ordered" (default), "unordered", or "sequential"
        user_segment: User segment - "active" (default) or "new"
        conversion_window_days: Time window for users to complete funnel (default 7 days, max 365)
        interval: Time interval (1=daily, 7=weekly, 30=monthly, -300000=realtime, -3600000=hourly)
        group_by: Optional property to segment by (e.g., 'country', 'gp:utm_campaign')
        segments: Optional segment definitions for filtering
        limit: Maximum number of group by values returned (default 100, max 1000)
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Dictionary containing:
        - stepByStep: Conversion rates between consecutive steps
        - cumulative: Overall conversion rates from first step
        - cumulativeRaw: Raw user counts for each step
        - medianTransTimes: Median time between steps (milliseconds)
        - avgTransTimes: Average time between steps (milliseconds)
        - events: Event labels for each funnel step
        - insights: Analysis of funnel performance and bottlenecks
    """
    # Validate inputs
    api_key, secret_key, error = get_api_credentials(api_key, secret_key)
    if error:
        return error
    
    date_error = validate_date_format(start_date, end_date)
    if date_error:
        return date_error
    
    # Validate events (minimum 2 for funnel analysis)
    events_error = validate_events_list(events, min_events=2, max_events=10)
    if events_error:
        return events_error
    
    mode_error = validate_funnel_mode(mode)
    if mode_error:
        return mode_error
    
    segment_error = validate_user_segment(user_segment)
    if segment_error:
        return segment_error
    
    interval_error = validate_funnel_interval(interval)
    if interval_error:
        return interval_error
    
    # Validate conversion window (convert days to seconds for API)
    if conversion_window_days < 1 or conversion_window_days > 365:
        return create_error_response(
            "Invalid conversion window",
            "Conversion window must be between 1 and 365 days"
        )
    
    conversion_window_seconds = conversion_window_days * 24 * 60 * 60  # Convert to seconds
    window_error = validate_funnel_conversion_window(conversion_window_seconds)
    if window_error:
        return window_error
    
    if limit < 1 or limit > 1000:
        return create_error_response(
            "Invalid limit",
            "Limit must be between 1 and 1000"
        )
    
    # Convert events to standard format
    formatted_events = _format_events(events)
    if "error" in formatted_events:
        return formatted_events
    
    client = AmplitudeClient(api_key, secret_key)
    
    try:
        # Make the API call
        result = await client.get_funnel_analysis(
            events=formatted_events["events"],
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            user_segment=user_segment,
            conversion_window_seconds=conversion_window_seconds,
            interval=interval,
            segments=segments,
            group_by=group_by,
            limit=limit,
            user_id="mcp_user"
        )
        
        # Process and enhance the response
        if "error" not in result:
            processed_result = _process_funnel_response(
                result,
                formatted_events["event_names"],
                mode,
                user_segment,
                conversion_window_days,
                start_date,
                end_date
            )
            return add_query_metadata(
                processed_result,
                "funnel_analysis",
                events=formatted_events["event_names"],
                mode=mode,
                user_segment=user_segment,
                conversion_window_days=conversion_window_days,
                date_range=f"{start_date}-{end_date}"
            )
        
        return result
        
    except Exception as e:
        return create_error_response(
            "Failed to get funnel analysis from Amplitude",
            str(e)
        )
    finally:
        await client.close()


def _format_events(events: List[Union[str, Dict[str, str]]]) -> Dict[str, Any]:
    """
    Format events into standard Amplitude format
    
    Args:
        events: List of events (strings or dicts)
        
    Returns:
        Dictionary with formatted events and event names, or error dict
    """
    try:
        formatted_events = []
        event_names = []
        
        for i, event in enumerate(events):
            if isinstance(event, str):
                # Simple event name
                formatted_events.append({"event_type": event})
                event_names.append(event)
            elif isinstance(event, dict) and "event_type" in event:
                # Already formatted event dict
                formatted_events.append(event)
                event_names.append(event["event_type"])
            else:
                return create_error_response(
                    "Invalid event format",
                    f"Event {i+1} must be a string or dict with 'event_type' key. Got: {type(event)}"
                )
        
        return {
            "events": formatted_events,
            "event_names": event_names
        }
        
    except Exception as e:
        return create_error_response(
            "Failed to format events",
            str(e)
        )


def _process_funnel_response(
    raw_response: Dict[str, Any],
    event_names: List[str],
    mode: str,
    user_segment: str,
    conversion_window_days: int,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Process the funnel API response into a clean format with insights
    
    Args:
        raw_response: Raw response from Amplitude Funnel API
        event_names: List of event names in funnel order
        mode: Funnel mode used
        user_segment: User segment analyzed
        conversion_window_days: Conversion window in days
        start_date: Start date
        end_date: End date
        
    Returns:
        Processed response with insights and clean formatting
    """
    try:
        data_array = raw_response.get("data", [])
        if not data_array:
            return create_error_response(
                "No funnel data returned",
                "Amplitude returned empty data array"
            )
        
        # Take the first data element (usually contains the main funnel)
        data = data_array[0] if isinstance(data_array, list) else data_array
        
        processed = {
            "success": True,
            "funnel_data": {
                "stepByStep": data.get("stepByStep", []),
                "cumulative": data.get("cumulative", []),
                "cumulativeRaw": data.get("cumulativeRaw", []),
                "medianTransTimes": data.get("medianTransTimes", []),
                "avgTransTimes": data.get("avgTransTimes", []),
                "events": data.get("events", event_names)
            },
            "summary": {
                "total_steps": len(event_names),
                "funnel_mode": mode,
                "user_segment": user_segment,
                "conversion_window_days": conversion_window_days,
                "date_range": f"{start_date} to {end_date}",
                "events_analyzed": event_names
            }
        }
        
        # Add advanced data if available
        if data.get("dayFunnels"):
            processed["daily_data"] = {
                "dayFunnels": data["dayFunnels"],
                "description": "Daily breakdown of users completing each funnel step"
            }
        
        if data.get("dayMedianTransTimes"):
            processed["daily_transition_times"] = {
                "dayMedianTransTimes": data["dayMedianTransTimes"],
                "dayAvgTransTimes": data.get("dayAvgTransTimes", {}),
                "description": "Daily median and average transition times between steps"
            }
        
        # Generate insights about funnel performance
        processed["insights"] = _generate_funnel_insights(processed, event_names)
        
        # Add conversion analysis
        processed["conversion_analysis"] = _analyze_funnel_conversion(
            processed["funnel_data"], event_names
        )
        
        return processed
        
    except Exception as e:
        return create_error_response(
            "Failed to process funnel response",
            str(e),
            raw_response=raw_response
        )


def _generate_funnel_insights(processed_data: Dict[str, Any], event_names: List[str]) -> List[str]:
    """
    Generate actionable insights about funnel performance
    
    Args:
        processed_data: Processed funnel data
        event_names: List of event names
        
    Returns:
        List of insight strings
    """
    insights = []
    
    try:
        funnel_data = processed_data.get("funnel_data", {})
        summary = processed_data.get("summary", {})
        
        step_by_step = funnel_data.get("stepByStep", [])
        cumulative = funnel_data.get("cumulative", [])
        cumulative_raw = funnel_data.get("cumulativeRaw", [])
        
        if not step_by_step or not cumulative_raw:
            insights.append("Funnel analysis completed - check raw data for details")
            return insights
        
        # Overall funnel performance
        total_users = cumulative_raw[0] if cumulative_raw else 0
        final_users = cumulative_raw[-1] if len(cumulative_raw) > 1 else 0
        overall_conversion = cumulative[-1] if cumulative else 0
        
        insights.append(f"Funnel analyzed {total_users:,} users across {len(event_names)} steps")
        insights.append(f"Overall conversion rate: {overall_conversion*100:.1f}% ({final_users:,} users completed)")
        
        # Find the biggest drop-off step
        if len(step_by_step) > 1:
            drop_offs = []
            for i in range(1, len(step_by_step)):
                drop_off = 1 - step_by_step[i]
                drop_offs.append((i, drop_off, event_names[i]))
            
            # Sort by drop-off rate (highest first)
            drop_offs.sort(key=lambda x: x[1], reverse=True)
            
            biggest_drop = drop_offs[0]
            step_idx, drop_rate, step_name = biggest_drop
            insights.append(f"Biggest drop-off: {drop_rate*100:.1f}% at step '{step_name}' (step {step_idx+1})")
        
        # Identify conversion rates between steps
        if len(step_by_step) > 1:
            best_step = max(range(1, len(step_by_step)), key=lambda i: step_by_step[i])
            worst_step = min(range(1, len(step_by_step)), key=lambda i: step_by_step[i])
            
            insights.append(f"Best step conversion: {step_by_step[best_step]*100:.1f}% at '{event_names[best_step]}'")
            insights.append(f"Worst step conversion: {step_by_step[worst_step]*100:.1f}% at '{event_names[worst_step]}'")
        
        # Funnel mode context
        mode = summary.get("funnel_mode", "ordered")
        if mode == "unordered":
            insights.append("Unordered funnel: users can complete steps in any sequence")
        elif mode == "sequential":
            insights.append("Sequential funnel: users must complete steps in exact order with no other events between")
        else:
            insights.append("Ordered funnel: users must complete steps in the specified sequence")
        
    except Exception:
        insights.append("Funnel analysis completed - review data for conversion opportunities")
    
    return insights


def _analyze_funnel_conversion(funnel_data: Dict[str, Any], event_names: List[str]) -> Dict[str, Any]:
    """
    Analyze funnel conversion rates and provide actionable metrics
    
    Args:
        funnel_data: Funnel data from API
        event_names: List of event names
        
    Returns:
        Dictionary with conversion analysis
    """
    try:
        step_by_step = funnel_data.get("stepByStep", [])
        cumulative_raw = funnel_data.get("cumulativeRaw", [])
        median_times = funnel_data.get("medianTransTimes", [])
        
        analysis = {
            "total_users_entered": cumulative_raw[0] if cumulative_raw else 0,
            "steps": []
        }
        
        for i in range(len(event_names)):
            step_analysis = {
                "step_number": i + 1,
                "event_name": event_names[i],
                "users_completed": cumulative_raw[i] if i < len(cumulative_raw) else 0,
                "cumulative_conversion_rate": step_by_step[i] if i < len(step_by_step) else 0,
            }
            
            # Add step-to-step conversion rate
            if i > 0 and i < len(step_by_step):
                step_analysis["step_conversion_rate"] = step_by_step[i]
                users_lost = cumulative_raw[i-1] - cumulative_raw[i] if i < len(cumulative_raw) else 0
                step_analysis["users_lost"] = users_lost
            
            # Add timing information
            if i < len(median_times) and median_times[i] > 0:
                # Convert milliseconds to readable format
                median_seconds = median_times[i] / 1000
                if median_seconds < 60:
                    step_analysis["median_time_to_step"] = f"{median_seconds:.1f} seconds"
                elif median_seconds < 3600:
                    step_analysis["median_time_to_step"] = f"{median_seconds/60:.1f} minutes"
                else:
                    step_analysis["median_time_to_step"] = f"{median_seconds/3600:.1f} hours"
            
            analysis["steps"].append(step_analysis)
        
        return analysis
        
    except Exception as e:
        return {"error": f"Failed to analyze conversion: {str(e)}"}