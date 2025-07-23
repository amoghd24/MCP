"""
Shared utilities for Amplitude tools
Provides common functionality to eliminate code repetition
"""

import os
from typing import Dict, Any, Optional, Tuple, Callable
from datetime import datetime
from functools import wraps

from .client import AmplitudeClient


def get_api_credentials(
    api_key: Optional[str] = None, 
    secret_key: Optional[str] = None
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """
    Get API credentials from parameters or environment variables
    
    Args:
        api_key: Optional API key
        secret_key: Optional secret key
        
    Returns:
        Tuple of (api_key, secret_key, error_dict)
        If error_dict is not None, credentials are missing
    """
    api_key = api_key or os.getenv("AMPLITUDE_API_KEY")
    secret_key = secret_key or os.getenv("AMPLITUDE_SECRET_KEY")
    
    if not api_key or not secret_key:
        error = {
            "error": "Missing Amplitude API credentials",
            "message": "Please provide api_key and secret_key, or set AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY environment variables"
        }
        return None, None, error
    
    return api_key, secret_key, None


def validate_date_format(start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
    """
    Validate date format (YYYYMMDD)
    
    Args:
        start_date: Start date string
        end_date: End date string
        
    Returns:
        Error dict if validation fails, None if valid
    """
    try:
        datetime.strptime(start_date, "%Y%m%d")
        datetime.strptime(end_date, "%Y%m%d")
        return None
    except ValueError:
        return {
            "error": "Invalid date format",
            "message": "Dates must be in YYYYMMDD format (e.g., '20240101')"
        }


def create_error_response(error_type: str, message: str, **kwargs) -> Dict[str, Any]:
    """
    Create standardized error response
    
    Args:
        error_type: Type of error
        message: Detailed error message
        **kwargs: Additional fields to include
        
    Returns:
        Standardized error response dict
    """
    response = {
        "error": error_type,
        "message": message
    }
    response.update(kwargs)
    return response


def validate_metric_type(metric: str, valid_metrics: list) -> Optional[Dict[str, Any]]:
    """
    Validate metric type against allowed values
    
    Args:
        metric: Metric to validate
        valid_metrics: List of valid metric values
        
    Returns:
        Error dict if invalid, None if valid
    """
    if metric not in valid_metrics:
        return create_error_response(
            "Invalid metric type",
            f"Metric must be one of: {', '.join(valid_metrics)}"
        )
    return None


def validate_interval(interval: int, valid_intervals: list) -> Optional[Dict[str, Any]]:
    """
    Validate interval against allowed values
    
    Args:
        interval: Interval to validate
        valid_intervals: List of valid interval values
        
    Returns:
        Error dict if invalid, None if valid
    """
    if interval not in valid_intervals:
        return create_error_response(
            "Invalid interval",
            f"Interval must be one of: {', '.join(map(str, valid_intervals))}"
        )
    return None


def validate_events_list(events: list, min_events: int = 1, max_events: int = 10) -> Optional[Dict[str, Any]]:
    """
    Validate events list length
    
    Args:
        events: List of events
        min_events: Minimum number of events required
        max_events: Maximum number of events allowed
        
    Returns:
        Error dict if invalid, None if valid
    """
    if len(events) < min_events:
        return create_error_response(
            "Insufficient events",
            f"At least {min_events} event(s) required"
        )
    
    if len(events) > max_events:
        return create_error_response(
            "Too many events",
            f"Maximum {max_events} events allowed"
        )
    
    return None


def amplitude_client_handler(func: Callable) -> Callable:
    """
    Decorator to handle Amplitude client creation and cleanup
    
    Args:
        func: Async function that needs an Amplitude client
        
    Returns:
        Wrapped function with automatic client management
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract API credentials from kwargs
        api_key = kwargs.pop('api_key', None)
        secret_key = kwargs.pop('secret_key', None)
        
        # Get credentials
        api_key, secret_key, error = get_api_credentials(api_key, secret_key)
        if error:
            return error
        
        # Create client
        client = AmplitudeClient(api_key, secret_key)
        
        try:
            # Call the original function with client
            return await func(client, *args, **kwargs)
        except Exception as e:
            return create_error_response(
                "API request failed",
                str(e)
            )
        finally:
            await client.close()
    
    return wrapper


def add_query_metadata(
    result: Dict[str, Any], 
    query_type: str, 
    **metadata
) -> Dict[str, Any]:
    """
    Add query metadata to successful API responses
    
    Args:
        result: API response dict
        query_type: Type of query performed
        **metadata: Additional metadata fields
        
    Returns:
        Enhanced result with metadata
    """
    if "error" not in result:
        result["query_info"] = {
            "query_type": query_type,
            **metadata
        }
    return result


def validate_conversion_window(window_days: int, min_days: int = 1, max_days: int = 365) -> Optional[Dict[str, Any]]:
    """
    Validate conversion window for funnel analysis
    
    Args:
        window_days: Conversion window in days
        min_days: Minimum allowed days
        max_days: Maximum allowed days
        
    Returns:
        Error dict if invalid, None if valid
    """
    if window_days < min_days or window_days > max_days:
        return create_error_response(
            "Invalid conversion window",
            f"Conversion window must be between {min_days} and {max_days} days"
        )
    return None


def validate_retention_type(retention_type: str) -> Optional[Dict[str, Any]]:
    """
    Validate retention analysis type
    
    Args:
        retention_type: Type of retention analysis
        
    Returns:
        Error dict if invalid, None if valid
    """
    valid_types = ["n_day", "rolling", "bracket", "unbounded"]
    if retention_type not in valid_types:
        return create_error_response(
            "Invalid retention type",
            f"Retention type must be one of: {', '.join(valid_types)}"
        )
    return None


def validate_funnel_mode(mode: str) -> Optional[Dict[str, Any]]:
    """
    Validate funnel mode
    
    Args:
        mode: Funnel mode to validate
        
    Returns:
        Error dict if invalid, None if valid
    """
    valid_modes = ["ordered", "unordered", "sequential"]
    if mode not in valid_modes:
        return create_error_response(
            "Invalid funnel mode",
            f"Funnel mode must be one of: {', '.join(valid_modes)}"
        )
    return None


def validate_user_segment(segment: str) -> Optional[Dict[str, Any]]:
    """
    Validate user segment for funnel analysis
    
    Args:
        segment: User segment to validate
        
    Returns:
        Error dict if invalid, None if valid
    """
    valid_segments = ["new", "active"]
    if segment not in valid_segments:
        return create_error_response(
            "Invalid user segment",
            f"User segment must be one of: {', '.join(valid_segments)}"
        )
    return None


def validate_funnel_interval(interval: int) -> Optional[Dict[str, Any]]:
    """
    Validate interval for funnel analysis
    
    Args:
        interval: Interval to validate
        
    Returns:
        Error dict if invalid, None if valid
    """
    valid_intervals = [-300000, -3600000, 1, 7, 30]
    if interval not in valid_intervals:
        return create_error_response(
            "Invalid funnel interval",
            f"Interval must be one of: {', '.join(map(str, valid_intervals))} (realtime, hourly, daily, weekly, monthly)"
        )
    return None


def validate_funnel_conversion_window(window_seconds: int) -> Optional[Dict[str, Any]]:
    """
    Validate conversion window for funnel analysis (in seconds)
    
    Args:
        window_seconds: Conversion window in seconds
        
    Returns:
        Error dict if invalid, None if valid
    """
    # Reasonable range: 1 hour to 1 year
    min_seconds = 3600  # 1 hour
    max_seconds = 31536000  # 1 year
    
    if window_seconds < min_seconds or window_seconds > max_seconds:
        return create_error_response(
            "Invalid conversion window",
            f"Conversion window must be between {min_seconds} and {max_seconds} seconds (1 hour to 1 year)"
        )
    return None