"""
Amplitude Event Segmentation API tool
Provides event segmentation analysis capabilities
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from .client import AmplitudeClient


async def get_amplitude_event_segmentation(
    events: List[str],
    start_date: str,
    end_date: str,
    metric: str = "uniques",
    user_type: str = "any",
    interval: str = "daily",
    segments: Optional[List[Dict[str, Any]]] = None,
    group_by: Optional[str] = None,
    group_by_2: Optional[str] = None,
    limit: int = 100,
    formula: Optional[str] = None,
    rolling_window: Optional[int] = None,
    rolling_average: Optional[int] = None,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get event segmentation data from Amplitude Dashboard API
    
    Args:
        events: List of event names (max 2)
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        metric: "uniques", "totals", "pct_dau", "average", "histogram", "sums", "value_avg", "formula"
        user_type: "any" or "active"
        interval: "daily", "weekly", "monthly", "hourly", "realtime"
        segments: Optional segment definitions
        group_by: Optional property to group by
        group_by_2: Optional second property to group by
        limit: Group by values returned (1-1000)
        formula: Required if metric is "formula"
        rolling_window: Rolling window in days/weeks/months
        rolling_average: Rolling average in days/weeks/months
        api_key: Amplitude API key
        secret_key: Amplitude secret key
    
    Returns:
        Dictionary with series, seriesLabels, seriesCollapsed, xValues
    """
    # Get credentials
    api_key = api_key or os.getenv("AMPLITUDE_API_KEY")
    secret_key = secret_key or os.getenv("AMPLITUDE_SECRET_KEY")
    
    if not api_key or not secret_key:
        return {"error": "Missing Amplitude API credentials"}
    
    # Validate inputs
    try:
        datetime.strptime(start_date, "%Y%m%d")
        datetime.strptime(end_date, "%Y%m%d")
    except ValueError:
        return {"error": "Dates must be in YYYYMMDD format"}
    
    if not events or len(events) > 2:
        return {"error": "Provide 1-2 events only"}
    
    valid_metrics = ["uniques", "totals", "pct_dau", "average", "histogram", "sums", "value_avg", "formula"]
    if metric not in valid_metrics:
        return {"error": f"Invalid metric. Use: {', '.join(valid_metrics)}"}
    
    if metric == "formula" and not formula:
        return {"error": "Formula required when metric is 'formula'"}
    
    if user_type not in ["any", "active"]:
        return {"error": "user_type must be 'any' or 'active'"}
    
    interval_map = {"realtime": -300000, "hourly": -3600000, "daily": 1, "weekly": 7, "monthly": 30}
    if interval not in interval_map:
        return {"error": f"Invalid interval. Use: {', '.join(interval_map.keys())}"}
    
    if not 1 <= limit <= 1000:
        return {"error": "Limit must be 1-1000"}
    
    # Make API call
    client = AmplitudeClient(api_key, secret_key)
    try:
        # Build parameters
        params = {
            "start": start_date,
            "end": end_date,
            "m": metric,
            "n": user_type,
            "i": interval_map[interval],
            "limit": limit
        }
        
        # Add events
        if len(events) >= 1:
            params["e"] = json.dumps({"event_type": events[0]})
        if len(events) >= 2:
            params["e2"] = json.dumps({"event_type": events[1]})
        
        # Add optional parameters
        if segments:
            params["s"] = json.dumps(segments)
        if group_by:
            params["g"] = group_by
        if group_by_2:
            params["g2"] = group_by_2
        if formula:
            params["formula"] = formula
        if rolling_window:
            params["rollingWindow"] = rolling_window
        if rolling_average:
            params["rollingAverage"] = rolling_average
        
        # Calculate cost and make request
        days = client._calculate_days(start_date, end_date)
        conditions = len(segments) if segments else 1
        base_cost = len(events) * 1
        group_cost = 4 * (bool(group_by) + bool(group_by_2))
        cost = client.calculate_cost(days, conditions, base_cost + group_cost)
        
        result = await client._make_request("events/segmentation", params, "mcp_user", cost)
        
        # Add metadata
        if "error" not in result:
            result["query_info"] = {
                "events": events,
                "start_date": start_date, 
                "end_date": end_date,
                "metric": metric,
                "user_type": user_type,
                "interval": interval,
                "query_type": "event_segmentation"
            }
        
        return result
        
    except Exception as e:
        return {"error": f"API request failed: {str(e)}"}
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
    Get event totals for multiple events (convenience function)
    
    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        events: List of event names
        api_key: Amplitude API key
        secret_key: Amplitude secret key
    
    Returns:
        Dictionary with event totals
    """
    
    if len(events) <= 2:
        # Single request
        result = await get_amplitude_event_segmentation(
            events=events,
            start_date=start_date,
            end_date=end_date,
            metric="totals",
            api_key=api_key,
            secret_key=secret_key
        )
        
        if "error" in result:
            return result
        
        # Extract totals
        totals = {}
        if "data" in result:
            series_collapsed = result["data"].get("seriesCollapsed", [])
            for i, event in enumerate(events):
                if i < len(series_collapsed) and series_collapsed[i]:
                    totals[event] = {
                        "total_events": series_collapsed[i][0].get("value", 0),
                        "metric_type": "totals"
                    }
        
        return {"success": True, "totals": totals}
    
    else:
        # Multiple requests for >2 events
        event_pairs = [events[i:i+2] for i in range(0, len(events), 2)]
        
        tasks = [
            get_amplitude_event_segmentation(
                events=pair,
                start_date=start_date,
                end_date=end_date,
                metric="totals",
                api_key=api_key,
                secret_key=secret_key
            )
            for pair in event_pairs
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        all_totals = {}
        failed_requests = []
        
        for i, result in enumerate(results):
            event_pair = event_pairs[i]
            
            if isinstance(result, Exception):
                failed_requests.extend([{"event": event, "error": str(result)} for event in event_pair])
            elif isinstance(result, dict) and "error" not in result and "data" in result:
                series_collapsed = result["data"].get("seriesCollapsed", [])
                for j, event in enumerate(event_pair):
                    if j < len(series_collapsed) and series_collapsed[j]:
                        all_totals[event] = {
                            "total_events": series_collapsed[j][0].get("value", 0),
                            "metric_type": "totals"
                        }
            elif isinstance(result, dict) and "error" in result:
                failed_requests.extend([{"event": event, "error": result["error"]} for event in event_pair])
        
        return {
            "success": True,
            "totals": all_totals,
            "processed_events": len(events),
            "failed_requests": failed_requests if failed_requests else None
        }