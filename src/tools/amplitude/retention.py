"""
Amplitude Retention Analysis API tool
Provides user retention and cohort analysis capabilities
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime

from .client import AmplitudeClient


async def get_amplitude_retention(
    start_event: str,
    return_event: str,
    start_date: str,
    end_date: str,
    retention_type: str = "n_day",
    interval: Optional[int] = None,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get retention analysis data from Amplitude Dashboard API
    
    Args:
        start_event: Initial event that defines the cohort (e.g., "App Opened", "_active", "_new")
        return_event: Event that defines user return/retention (e.g., "App Opened", "_all", "_active")
        start_date: Start date in YYYYMMDD format (e.g., "20240101")
        end_date: End date in YYYYMMDD format (e.g., "20240131")
        retention_type: Type of retention analysis ("n_day", "rolling", "bracket")
        interval: Optional interval (1=daily, 7=weekly, 30=monthly)
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Dictionary containing retention analysis data
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
    
    if not start_event or not return_event:
        return {
            "error": "Missing events",
            "message": "Both start_event and return_event must be specified"
        }
    
    client = AmplitudeClient(api_key, secret_key)
    
    try:
        # Convert events to Amplitude format
        start_event_def = {"event_type": start_event}
        return_event_def = {"event_type": return_event}
        
        # Make the API call
        result = await client.get_retention_analysis(
            start_event=start_event_def,
            return_event=return_event_def,
            start_date=start_date,
            end_date=end_date,
            retention_type=retention_type,
            interval=interval,
            user_id="mcp_user"
        )
        
        # Add formatted retention table if data is available
        if "error" not in result and "data" in result:
            result["formatted_table"] = _format_retention_table(result["data"])
        
        return result
        
    except Exception as e:
        return {
            "error": "Failed to get retention analysis data",
            "message": str(e)
        }
    finally:
        await client.close()


def _format_retention_table(data: Dict[str, Any]) -> str:
    """
    Format retention data into a table matching the UI format
    
    Args:
        data: Raw retention data from Amplitude API
    
    Returns:
        Formatted retention table as string
    """
    try:
        series = data.get("series", [])
        if not series:
            return "No retention data available"
        
        first_series = series[0]
        dates = first_series.get("dates", [])
        values = first_series.get("values", {})
        combined = first_series.get("combined", [])
        
        lines = []
        
        # Add combined total row first
        if combined:
            total_users = combined[0].get("outof", 0)
            retention_data = []
            
            for i, period in enumerate(combined):
                count = period.get("count", 0)
                outof = period.get("outof", 0)
                incomplete = period.get("incomplete", False)
                
                if outof > 0:
                    percent = round((count / outof) * 100, 2)
                    marker = "*" if incomplete else ""
                    retention_data.append(f"{marker}{percent}% {count} User(s)")
                else:
                    retention_data.append("0.0% 0 User(s)")
            
            combined_line = f"0\t{total_users}\t100%\t" + "\t".join(retention_data)
            lines.append(combined_line)
        
        # Add individual cohort rows
        for date in dates:
            if date not in values:
                continue
                
            cohort_data = values[date]
            if not cohort_data:
                continue
                
            initial_users = cohort_data[0].get("outof", 0)
            retention_periods = []
            
            # Skip the first two entries (both Day 0 - 100%) and process retention periods
            for i in range(1, len(cohort_data)):
                period = cohort_data[i]
                count = period.get("count", 0)
                outof = period.get("outof", 0)
                incomplete = period.get("incomplete", False)
                
                if outof > 0:
                    percent = round((count / outof) * 100, 2)
                    marker = "*" if incomplete else ""
                    retention_periods.append(f"{marker}{percent}% {count} User(s)")
                else:
                    retention_periods.append("0.0% 0 User(s)")
            
            cohort_line = f"{date}\t{initial_users}\t100%\t" + "\t".join(retention_periods)
            lines.append(cohort_line)
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error formatting retention table: {str(e)}"