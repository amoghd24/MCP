"""
Amplitude Retention Analysis API tool
Provides user retention and cohort analysis capabilities
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime

from .client import AmplitudeClient


async def get_amplitude_retention(
    start_event: str,
    return_event: str,
    start_date: str,
    end_date: str,
    retention_type: str = "retention_N_day",
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get retention analysis data from Amplitude Dashboard API
    
    Args:
        start_event: Initial event that defines the cohort
        return_event: Event that defines user return/retention
        start_date: Start date in YYYYMMDD format (e.g., "20240101")
        end_date: End date in YYYYMMDD format (e.g., "20240131")
        retention_type: Type of retention analysis:
            - "retention_N_day": N-day retention
            - "retention_bracket": Bracket retention
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Dictionary containing retention analysis data including:
        - Retention curves and cohort data
        - Retention rates over time periods
        - User counts for each cohort
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
    
    # Validate retention type
    valid_retention_types = ["retention_N_day", "retention_bracket"]
    if retention_type not in valid_retention_types:
        return {
            "error": "Invalid retention type",
            "message": f"Retention type must be one of: {', '.join(valid_retention_types)}"
        }
    
    # Validate events
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
            user_id="mcp_user"  # Default user ID for rate limiting
        )
        
        # Add metadata and enhanced analysis to response
        if "error" not in result:
            result["query_info"] = {
                "start_event": start_event,
                "return_event": return_event,
                "start_date": start_date,
                "end_date": end_date,
                "retention_type": retention_type,
                "query_type": "retention_analysis"
            }
            
            # Add retention insights if data is available
            if "data" in result:
                result["retention_insights"] = _analyze_retention_data(result["data"], retention_type)
        
        return result
        
    except Exception as e:
        return {
            "error": "Failed to get retention analysis data",
            "message": str(e)
        }
    finally:
        await client.close()


async def get_amplitude_cohort_retention(
    start_event: str,
    return_event: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get cohort retention analysis (N-day retention)
    
    Args:
        start_event: Initial event that defines the cohort
        return_event: Event that defines user return/retention
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        api_key: Amplitude API key (optional)
        secret_key: Amplitude secret key (optional)
    
    Returns:
        Dictionary with cohort retention data and insights
    """
    result = await get_amplitude_retention(
        start_event=start_event,
        return_event=return_event,
        start_date=start_date,
        end_date=end_date,
        retention_type="retention_N_day",
        api_key=api_key,
        secret_key=secret_key
    )
    
    if "error" in result:
        return result
    
    try:
        if "retention_insights" in result:
            return {
                "success": True,
                "cohort_analysis": result["retention_insights"],
                "query_info": result.get("query_info", {}),
                "raw_data": result.get("data", {})
            }
        else:
            return {
                "success": True,
                "message": "Retention data retrieved but insights not available",
                "raw_result": result
            }
            
    except Exception as e:
        return {
            "error": "Failed to generate cohort retention analysis",
            "message": str(e),
            "raw_result": result
        }


async def get_amplitude_retention_summary(
    start_event: str,
    return_event: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a retention summary with key metrics
    
    Args:
        start_event: Initial event that defines the cohort
        return_event: Event that defines user return/retention
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        api_key: Amplitude API key (optional)
        secret_key: Amplitude secret key (optional)
    
    Returns:
        Dictionary with key retention metrics and summary
    """
    result = await get_amplitude_retention(
        start_event=start_event,
        return_event=return_event,
        start_date=start_date,
        end_date=end_date,
        retention_type="retention_N_day",
        api_key=api_key,
        secret_key=secret_key
    )
    
    if "error" in result:
        return result
    
    try:
        summary = {
            "success": True,
            "start_event": start_event,
            "return_event": return_event,
            "date_range": f"{start_date} to {end_date}",
            "key_metrics": {}
        }
        
        # Extract key metrics if retention insights are available
        if "retention_insights" in result:
            insights = result["retention_insights"]
            
            summary["key_metrics"] = {
                "day_1_retention": insights.get("day_1_retention", "N/A"),
                "day_7_retention": insights.get("day_7_retention", "N/A"),
                "day_30_retention": insights.get("day_30_retention", "N/A"),
                "total_cohort_size": insights.get("total_cohort_size", "N/A"),
                "retention_trend": insights.get("retention_trend", "N/A")
            }
        
        # Add query info
        summary["query_info"] = result.get("query_info", {})
        
        return summary
        
    except Exception as e:
        return {
            "error": "Failed to generate retention summary",
            "message": str(e),
            "raw_result": result
        }


def _analyze_retention_data(retention_data: Dict[str, Any], retention_type: str) -> Dict[str, Any]:
    """
    Analyze retention data to extract key insights
    
    Args:
        retention_data: Raw retention data from Amplitude API
        retention_type: Type of retention analysis
    
    Returns:
        Dictionary with retention insights
    """
    try:
        insights = {
            "retention_type": retention_type,
            "analysis_summary": "Retention analysis completed"
        }
        
        # Extract cohort data if available
        if "series" in retention_data:
            series_data = retention_data["series"]
            
            # Try to extract retention rates for common time periods
            retention_rates = {}
            total_users = 0
            
            # Process series data (structure varies by Amplitude API response)
            if isinstance(series_data, list) and len(series_data) > 0:
                first_series = series_data[0]
                
                if "values" in first_series:
                    values = first_series["values"]
                    
                    # Map common retention periods
                    if len(values) > 0:
                        total_users = values[0]  # Day 0 (initial cohort)
                        insights["total_cohort_size"] = total_users
                    
                    # Extract retention for key days if available
                    retention_periods = {
                        "day_1_retention": 1,
                        "day_7_retention": 7,
                        "day_30_retention": 30
                    }
                    
                    for period_name, day_index in retention_periods.items():
                        if day_index < len(values) and total_users > 0:
                            retained_users = values[day_index]
                            retention_rate = (retained_users / total_users) * 100
                            retention_rates[period_name] = round(retention_rate, 2)
                        else:
                            retention_rates[period_name] = "N/A"
            
            insights.update(retention_rates)
            
            # Analyze retention trend
            if retention_rates:
                available_rates = [v for v in retention_rates.values() if v != "N/A"]
                if len(available_rates) >= 2:
                    if available_rates[-1] < available_rates[0]:
                        insights["retention_trend"] = "declining"
                    elif available_rates[-1] > available_rates[0]:
                        insights["retention_trend"] = "improving"
                    else:
                        insights["retention_trend"] = "stable"
                else:
                    insights["retention_trend"] = "insufficient_data"
        
        # Add recommendations based on retention rates
        insights["recommendations"] = _generate_retention_recommendations(insights)
        
        return insights
        
    except Exception as e:
        return {
            "error": "Failed to analyze retention data",
            "message": str(e)
        }


def _generate_retention_recommendations(insights: Dict[str, Any]) -> List[str]:
    """
    Generate retention improvement recommendations based on the data
    
    Args:
        insights: Retention insights dictionary
    
    Returns:
        List of recommendation strings
    """
    recommendations = []
    
    try:
        # Day 1 retention recommendations
        day_1 = insights.get("day_1_retention", "N/A")
        if day_1 != "N/A" and isinstance(day_1, (int, float)):
            if day_1 < 20:
                recommendations.append("Day 1 retention is low (<20%) - Focus on onboarding experience")
            elif day_1 < 40:
                recommendations.append("Day 1 retention is moderate - Consider improving first-use experience")
        
        # Day 7 retention recommendations  
        day_7 = insights.get("day_7_retention", "N/A")
        if day_7 != "N/A" and isinstance(day_7, (int, float)):
            if day_7 < 10:
                recommendations.append("Day 7 retention is low (<10%) - Implement re-engagement campaigns")
            elif day_7 < 25:
                recommendations.append("Day 7 retention needs improvement - Focus on habit formation")
        
        # Trend-based recommendations
        trend = insights.get("retention_trend", "")
        if trend == "declining":
            recommendations.append("Retention is declining - Investigate recent product changes")
        elif trend == "improving":
            recommendations.append("Retention is improving - Continue current strategies")
        
        # Default recommendation if no specific insights
        if not recommendations:
            recommendations.append("Monitor retention trends regularly and A/B test retention strategies")
    
    except Exception:
        recommendations.append("Unable to generate specific recommendations - review retention data manually")
    
    return recommendations