"""
Amplitude Event Segmentation API tool
Provides event segmentation analysis with breakdown by properties
"""

from typing import Dict, Any, Optional, List

from .client import AmplitudeClient
from .utils import (
    get_api_credentials,
    validate_date_format,
    validate_events_list,
    validate_metric_type,
    validate_interval,
    create_error_response,
    add_query_metadata
)


async def get_amplitude_event_segmentation(
    events: List[Dict[str, str]],
    start_date: str,
    end_date: str,
    metric: str = "uniques",
    group_by: Optional[str] = None,
    group_by_2: Optional[str] = None,
    segments: Optional[List[Dict[str, Any]]] = None,
    interval: int = 1,
    limit: int = 100,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get event segmentation data from Amplitude with property breakdown
    
    Args:
        events: List of event definitions (1-2 events). Each event should have 'event_type' key
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        metric: Metric type - 'uniques', 'totals', 'pct_dau', 'average', 'histogram', 'sums', 'value_avg', or 'formula'
        group_by: Property to segment by (e.g., 'country', 'gp:utm_campaign')
        group_by_2: Second property to segment by (optional)
        segments: Optional segment definitions for filtering
        interval: Time interval (1=daily, 7=weekly, 30=monthly, -300000=realtime, -3600000=hourly)
        limit: Maximum number of group by values returned (default 100, max 1000)
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Dictionary containing:
        - series: Array of metric values for each segment over time
        - seriesLabels: Names of each segment
        - seriesCollapsed: Total values for each segment
        - xValues: Date array for the time period
        - insights: Analysis of the segmentation data
    """
    # Validate inputs
    api_key, secret_key, error = get_api_credentials(api_key, secret_key)
    if error:
        return error
    
    date_error = validate_date_format(start_date, end_date)
    if date_error:
        return date_error
    
    events_error = validate_events_list(events, min_events=1, max_events=2)
    if events_error:
        return events_error
    
    valid_metrics = ["uniques", "totals", "pct_dau", "average", "histogram", "sums", "value_avg", "formula"]
    metric_error = validate_metric_type(metric, valid_metrics)
    if metric_error:
        return metric_error
    
    valid_intervals = [1, 7, 30, -300000, -3600000]
    interval_error = validate_interval(interval, valid_intervals)
    if interval_error:
        return interval_error
    
    if limit < 1 or limit > 1000:
        return create_error_response(
            "Invalid limit",
            "Limit must be between 1 and 1000"
        )
    
    # Validate events have required structure
    for i, event in enumerate(events):
        if not isinstance(event, dict) or "event_type" not in event:
            return create_error_response(
                "Invalid event format",
                f"Event {i+1} must be a dictionary with 'event_type' key"
            )
    
    client = AmplitudeClient(api_key, secret_key)
    
    try:
        # Build parameters for segmentation API
        params = {
            "start": start_date,
            "end": end_date,
            "m": metric,
            "i": interval,
            "limit": limit
        }
        
        # Add events (max 2)
        if len(events) == 1:
            params["e"] = {"event_type": events[0]["event_type"]}
        else:  # len(events) == 2
            params["e"] = {"event_type": events[0]["event_type"]}
            params["e2"] = {"event_type": events[1]["event_type"]}
        
        # Add group by properties
        if group_by:
            params["g"] = group_by
        if group_by_2:
            params["g2"] = group_by_2
        
        # Add segments if provided
        if segments:
            params["s"] = segments
        
        # Make API request
        result = await client.get_event_segmentation(
            start_date=start_date,
            end_date=end_date,
            events=events,
            segments=segments,
            group_by=group_by,
            interval=interval,
            user_id="mcp_user"
        )
        
        # Process and enhance the response
        if "error" not in result:
            processed_result = _process_segmentation_response(
                result, 
                events, 
                metric, 
                group_by,
                group_by_2,
                start_date, 
                end_date
            )
            return add_query_metadata(
                processed_result,
                "event_segmentation",
                events=[e["event_type"] for e in events],
                metric=metric,
                group_by=group_by,
                group_by_2=group_by_2,
                date_range=f"{start_date}-{end_date}"
            )
        
        return result
        
    except Exception as e:
        return create_error_response(
            "Failed to get event segmentation from Amplitude",
            str(e)
        )
    finally:
        await client.close()


async def get_amplitude_event_segmentation_simple(
    event_name: str,
    start_date: str,
    end_date: str,
    group_by: str,
    metric: str = "uniques",
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Simplified event segmentation for a single event with one group by property
    
    Args:
        event_name: Name of the event to analyze
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        group_by: Property to segment by (e.g., 'country', 'device_type')
        metric: Metric type (default: 'uniques')
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Simplified segmentation data with insights
    """
    events = [{"event_type": event_name}]
    
    return await get_amplitude_event_segmentation(
        events=events,
        start_date=start_date,
        end_date=end_date,
        metric=metric,
        group_by=group_by,
        api_key=api_key,
        secret_key=secret_key
    )


def _process_segmentation_response(
    raw_response: Dict[str, Any],
    events: List[Dict[str, str]],
    metric: str,
    group_by: Optional[str],
    group_by_2: Optional[str],
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Process the segmentation API response into a clean format
    
    Args:
        raw_response: Raw response from Amplitude Segmentation API
        events: Original events list
        metric: Metric type used
        group_by: Group by property
        group_by_2: Second group by property
        start_date: Start date
        end_date: End date
        
    Returns:
        Processed response with insights and clean formatting
    """
    try:
        data = raw_response.get("data", {})
        
        processed = {
            "success": True,
            "data": {
                "series": data.get("series", []),
                "seriesLabels": data.get("seriesLabels", []),
                "seriesCollapsed": data.get("seriesCollapsed", []),
                "xValues": data.get("xValues", [])
            },
            "summary": {
                "total_segments": len(data.get("seriesLabels", [])),
                "date_range": f"{start_date} to {end_date}",
                "events_analyzed": [e["event_type"] for e in events],
                "metric_type": metric,
                "group_by_properties": [prop for prop in [group_by, group_by_2] if prop]
            }
        }
        
        # Add insights
        processed["insights"] = _generate_segmentation_insights(processed, metric)
        
        # Add top segments analysis
        if data.get("seriesCollapsed") and data.get("seriesLabels"):
            processed["top_segments"] = _analyze_top_segments(
                data["seriesCollapsed"], 
                data["seriesLabels"], 
                metric
            )
        
        return processed
        
    except Exception as e:
        return create_error_response(
            "Failed to process segmentation response",
            str(e),
            raw_response=raw_response
        )


def _generate_segmentation_insights(processed_data: Dict[str, Any], metric: str) -> List[str]:
    """
    Generate insights based on segmentation data
    
    Args:
        processed_data: Processed segmentation data
        metric: Metric type used
        
    Returns:
        List of insight strings
    """
    insights = []
    
    try:
        data = processed_data.get("data", {})
        summary = processed_data.get("summary", {})
        
        total_segments = summary.get("total_segments", 0)
        events = summary.get("events_analyzed", [])
        group_by_props = summary.get("group_by_properties", [])
        
        if total_segments == 0:
            insights.append("No segments found - check your group by property and date range")
            return insights
        
        # Basic overview
        event_names = ", ".join(events)
        group_by_text = " and ".join(group_by_props) if group_by_props else "overall"
        insights.append(f"Found {total_segments} segments for {event_names} grouped by {group_by_text}")
        
        # Metric-specific insights
        if metric == "uniques":
            insights.append("Showing unique users per segment over time")
        elif metric == "totals":
            insights.append("Showing total event occurrences per segment")
        elif metric == "pct_dau":
            insights.append("Showing percentage of daily active users per segment")
        elif metric == "average":
            insights.append("Showing average values per segment")
        
        # Time series analysis
        x_values = data.get("xValues", [])
        if len(x_values) > 1:
            insights.append(f"Time series data available for {len(x_values)} data points")
        else:
            insights.append("Single time point analysis")
        
        insights.append("Use top_segments for ranked performance analysis")
        
    except Exception:
        insights.append("Segmentation analysis completed successfully")
    
    return insights


def _analyze_top_segments(
    series_collapsed: List[List[Dict[str, Any]]], 
    series_labels: List[str], 
    metric: str
) -> List[Dict[str, Any]]:
    """
    Analyze top performing segments
    
    Args:
        series_collapsed: Collapsed series data from API
        series_labels: Segment labels
        metric: Metric type
        
    Returns:
        List of top segments with analysis
    """
    try:
        segments = []
        
        for i, (collapsed_data, label) in enumerate(zip(series_collapsed, series_labels)):
            if collapsed_data and len(collapsed_data) > 0:
                value = collapsed_data[0].get("value", 0) if isinstance(collapsed_data[0], dict) else collapsed_data[0]
                
                segments.append({
                    "rank": i + 1,
                    "segment": label,
                    "value": value,
                    "metric": metric
                })
        
        # Sort by value descending
        segments.sort(key=lambda x: x["value"], reverse=True)
        
        # Update ranks
        for i, segment in enumerate(segments):
            segment["rank"] = i + 1
        
        return segments[:10]  # Return top 10
        
    except Exception:
        return []