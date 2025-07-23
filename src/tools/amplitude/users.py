"""
Amplitude User Count API tool
Provides active and new user count capabilities
"""

from typing import Dict, Any, Optional

from .client import AmplitudeClient
from .utils import (
    get_api_credentials,
    validate_date_format,
    validate_metric_type,
    validate_interval,
    create_error_response
)


async def get_amplitude_users(
    start_date: str,
    end_date: str,
    metric: str = "active",
    interval: int = 1,
    segment_definitions: Optional[Dict[str, Any]] = None,
    group_by: Optional[str] = None,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get active or new user counts from Amplitude Dashboard API
    
    Args:
        start_date: Start date in YYYYMMDD format (e.g., "20240101")
        end_date: End date in YYYYMMDD format (e.g., "20240131")
        metric: Either "active" or "new" to get the desired count. Defaults to "active"
        interval: Either 1, 7, or 30 for daily, weekly, and monthly counts, respectively. Defaults to 1
        segment_definitions: Optional segment definitions to filter users
        group_by: Optional property to group by (e.g., "city", "country")
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Dictionary containing user count data with formatted results
    """
    # Get API credentials
    api_key, secret_key, error = get_api_credentials(api_key, secret_key)
    if error:
        return error
    
    # Validate inputs
    date_error = validate_date_format(start_date, end_date)
    if date_error:
        return date_error
    
    metric_error = validate_metric_type(metric, ["active", "new"])
    if metric_error:
        return metric_error
    
    interval_error = validate_interval(interval, [1, 7, 30])
    if interval_error:
        return interval_error
    
    client = AmplitudeClient(api_key, secret_key)
    
    try:
        # Make the API call
        result = await client.get_user_counts(
            start_date=start_date,
            end_date=end_date,
            metric=metric,
            interval=interval,
            segment_definitions=segment_definitions,
            group_by=group_by,
            user_id="mcp_user"
        )
        
        # Add formatted summary if data is available
        if "error" not in result and "data" in result:
            result["formatted_summary"] = _format_user_counts(result["data"], metric, interval)
        
        return result
        
    except Exception as e:
        return create_error_response(
            "Failed to get user count data",
            str(e)
        )
    finally:
        await client.close()


def _format_user_counts(data: Dict[str, Any], metric: str, interval: int) -> str:
    """
    Format user count data into a readable summary
    
    Args:
        data: Raw user count data from Amplitude API
        metric: The metric type ("active" or "new")
        interval: The interval (1, 7, or 30)
    
    Returns:
        Formatted user count summary as string
    """
    try:
        series = data.get("series", [])
        series_meta = data.get("seriesMeta", [])
        x_values = data.get("xValues", [])
        
        if not series or not x_values:
            return "No user count data available"
        
        # Determine interval description
        interval_desc = {1: "Daily", 7: "Weekly", 30: "Monthly"}.get(interval, "Daily")
        metric_desc = metric.title()
        
        lines = [f"{interval_desc} {metric_desc} User Counts", "=" * 40]
        
        # If there are multiple series (grouped data)
        if len(series) > 1 and len(series_meta) > 0:
            for i, (series_data, group_name) in enumerate(zip(series, series_meta)):
                lines.append(f"\nGroup: {group_name}")
                lines.append("-" * 20)
                
                for date, count in zip(x_values, series_data):
                    lines.append(f"{date}: {count:,} users")
                
                # Add totals for this group
                total = sum(series_data) if series_data else 0
                avg = total / len(series_data) if series_data else 0
                lines.append(f"Total: {total:,} users")
                lines.append(f"Average: {avg:,.1f} users")
        
        # Single series (no grouping)
        else:
            series_data = series[0] if series else []
            for date, count in zip(x_values, series_data):
                lines.append(f"{date}: {count:,} users")
            
            # Add summary statistics
            if series_data:
                total = sum(series_data)
                avg = total / len(series_data)
                max_users = max(series_data)
                min_users = min(series_data)
                
                lines.extend([
                    "",
                    "Summary Statistics:",
                    f"Total: {total:,} users",
                    f"Average: {avg:,.1f} users",
                    f"Maximum: {max_users:,} users", 
                    f"Minimum: {min_users:,} users"
                ])
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error formatting user count data: {str(e)}" 