"""
Amplitude Analytics API Client
Handles authentication, rate limiting, and API communication
"""

import base64
import json
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urlencode, quote

from src.utils.rate_limiter import api_rate_limiter


# Special event types for retention analysis
RETENTION_SPECIAL_EVENTS = {
    "new_users": "_new",
    "active_users": "_active", 
    "all_events": "_all"
}

# Valid retention modes
RETENTION_MODES = {
    "n_day": None,  # Default - omit parameter
    "rolling": "rolling",  # Rolling retention
    "bracket": "bracket",  # Bracket retention  
    "unbounded": "unbounded"  # Unbounded retention
}


class AmplitudeClient:
    """Client for Amplitude Dashboard REST API"""
    
    def __init__(self, api_key: str, secret_key: str):
        """Initialize Amplitude client with API credentials
        
        Args:
            api_key: Amplitude API key
            secret_key: Amplitude secret key
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://amplitude.com/api/2"
        
        # Create base64 encoded credentials for basic auth
        credentials = f"{api_key}:{secret_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=30.0,
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2)
        )
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    def calculate_cost(self, days: int, conditions: int, query_type_cost: int) -> int:
        """Calculate API call cost using Amplitude's formula
        
        Args:
            days: Number of days in query
            conditions: Number of conditions/segments
            query_type_cost: Base cost for query type
            
        Returns:
            Total cost for the query
        """
        return api_rate_limiter.calculate_amplitude_cost(days, conditions, query_type_cost)
    
    def _calculate_days(self, start_date: str, end_date: str) -> int:
        """Calculate number of days between start and end date
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            
        Returns:
            Number of days
        """
        try:
            start = datetime.strptime(start_date, "%Y%m%d")
            end = datetime.strptime(end_date, "%Y%m%d")
            return (end - start).days + 1  # Include both start and end dates
        except ValueError:
            # Default to 1 day if parsing fails
            return 1
    
    async def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        user_id: str = "default",
        cost: int = 1
    ) -> Dict[str, Any]:
        """Make authenticated request to Amplitude API with rate limiting
        
        Args:
            endpoint: API endpoint (e.g., "events/segmentation")
            params: Query parameters
            user_id: User ID for rate limiting
            cost: Cost of the query for rate limiting
            
        Returns:
            API response as dictionary
        """
        # Check and start rate limiting
        if not api_rate_limiter.start_amplitude_request(user_id, cost):
            return {
                "error": "Rate limit exceeded. Too many concurrent requests or cost limit reached.",
                "details": "Amplitude allows max 5 concurrent requests and 12000 cost per hour"
            }
        
        try:
            url = f"{self.base_url}/{endpoint}"
            
            # Manually build URL with properly encoded parameters
            if params:
                # Special handling for JSON parameters - ensure proper encoding
                encoded_params = []
                for key, value in params.items():
                    if isinstance(value, dict):
                        # JSON parameters need to be serialized then encoded
                        json_str = json.dumps(value, separators=(',', ':'))
                        encoded_params.append(f"{key}={quote(json_str, safe='')}")
                    elif isinstance(value, list):
                        # Handle list parameters (like multiple 'e' params for funnels)
                        for item in value:
                            if isinstance(item, dict):
                                json_str = json.dumps(item, separators=(',', ':'))
                                encoded_params.append(f"{key}={quote(json_str, safe='')}")
                            else:
                                encoded_params.append(f"{key}={quote(str(item), safe='')}")
                    else:
                        # Regular parameters
                        encoded_params.append(f"{key}={quote(str(value), safe='')}")
                
                url = f"{url}?{'&'.join(encoded_params)}"
            
            response = await self.client.get(url)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                return {
                    "error": "Rate limit exceeded",
                    "status_code": 429,
                    "message": "Amplitude API rate limit reached"
                }
            elif response.status_code == 401:
                return {
                    "error": "Authentication failed",
                    "status_code": 401,
                    "message": "Invalid API key or secret key"
                }
            else:
                # Try to parse error response
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", error_json.get("message", response.text))
                except:
                    pass
                
                return {
                    "error": f"API request failed",
                    "status_code": response.status_code,
                    "message": error_detail,
                    "url": url  # Include URL for debugging
                }
                
        except httpx.TimeoutException:
            return {
                "error": "Request timeout",
                "message": "Amplitude API request timed out after 30 seconds"
            }
        except Exception as e:
            return {
                "error": "Request failed",
                "message": str(e)
            }
        finally:
            # Always end rate limiting tracking
            api_rate_limiter.end_amplitude_request(user_id)
    
    async def get_event_segmentation(
        self,
        start_date: str,
        end_date: str,
        events: List[Dict[str, Any]],
        segments: Optional[List[Dict[str, Any]]] = None,
        group_by: Optional[str] = None,
        interval: int = 1,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Get event segmentation data
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            events: List of event definitions (up to 2)
            segments: Optional list of segments
            group_by: Optional property to group by
            interval: Interval (1=daily, 7=weekly, 30=monthly)
            user_id: User ID for rate limiting
            
        Returns:
            Event segmentation data
        """
        # Calculate cost: # of events * 1 (+ 4 per group_by)
        days = self._calculate_days(start_date, end_date)
        conditions = len(segments) if segments else 1
        base_cost = len(events) * 1
        group_cost = 4 if group_by else 0
        cost = self.calculate_cost(days, conditions, base_cost + group_cost)
        
        # Format events properly for Amplitude API
        # For single event: e={"event_type": "event_name"}
        # For two events: e={"event_type": "event1"}&e2={"event_type": "event2"}
        params = {
            "start": start_date,
            "end": end_date,
            "i": interval
        }
        
        if len(events) == 1:
            params["e"] = json.dumps({"event_type": events[0]["event_type"]})
        elif len(events) == 2:
            params["e"] = json.dumps({"event_type": events[0]["event_type"]})
            params["e2"] = json.dumps({"event_type": events[1]["event_type"]})
        else:
            # Amplitude Event Segmentation only supports up to 2 events
            raise ValueError("Event Segmentation API supports maximum 2 events")
        
        if segments:
            params["s"] = segments
        if group_by:
            params["g"] = group_by
        
        return await self._make_request("events/segmentation", params, user_id, cost)
    
    async def get_funnel_analysis(
        self,
        events: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
        segments: Optional[List[Dict[str, Any]]] = None,
        group_by: Optional[str] = None,
        conversion_window_days: int = 7,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Get funnel analysis data
        
        Args:
            events: List of funnel step events
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            segments: Optional list of segments
            group_by: Optional property to group by
            conversion_window_days: Conversion window in days
            user_id: User ID for rate limiting
            
        Returns:
            Funnel analysis data
        """
        # Calculate cost: (# of events * 2) + (4 per group_by)
        days = self._calculate_days(start_date, end_date)
        conditions = len(segments) if segments else 1
        base_cost = len(events) * 2
        group_cost = 4 if group_by else 0
        cost = self.calculate_cost(days, conditions, base_cost + group_cost)
        
        # Format events for funnel analysis - use multiple e parameters
        params = {
            "start": start_date,
            "end": end_date,
            "cs": conversion_window_days * 24  # Convert days to hours
        }
        
        # Add events as multiple e parameters - funnel format uses repeated "e"
        # httpx will automatically create multiple e= parameters from this list
        params["e"] = [json.dumps({"event_type": event["event_type"]}) for event in events]
        
        if segments:
            params["s"] = segments
        if group_by:
            params["g"] = group_by
        
        return await self._make_request("funnels", params, user_id, cost)
    
    async def get_retention_analysis(
        self,
        start_event: Dict[str, Any],
        return_event: Dict[str, Any],
        start_date: str,
        end_date: str,
        retention_type: str = "n_day",
        interval: Optional[int] = None,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Get retention analysis data
        
        Args:
            start_event: Starting event definition (can be special type or event name)
            return_event: Return event definition (can be special type or event name)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            retention_type: Type of retention analysis (n_day, rolling, bracket, unbounded)
            interval: Optional interval (1=daily, 7=weekly, 30=monthly) for N-day retention
            user_id: User ID for rate limiting
            
        Returns:
            Retention analysis data
        """
        # Calculate cost: Fixed cost of 8
        days = self._calculate_days(start_date, end_date)
        cost = self.calculate_cost(days, 1, 8)
        
        # Handle special event types and format for retention analysis
        start_event_type = start_event.get("event_type", "")
        return_event_type = return_event.get("event_type", "")
        
        # Check if using special event types
        if start_event_type in RETENTION_SPECIAL_EVENTS.values():
            # Already a special event type, use as-is
            start_event_formatted = {"event_type": start_event_type}
        elif start_event_type in RETENTION_SPECIAL_EVENTS:
            # Convert from friendly name to API value
            start_event_formatted = {"event_type": RETENTION_SPECIAL_EVENTS[start_event_type]}
        else:
            # Regular event name
            start_event_formatted = {"event_type": start_event_type}
        
        if return_event_type in RETENTION_SPECIAL_EVENTS.values():
            # Already a special event type, use as-is
            return_event_formatted = {"event_type": return_event_type}
        elif return_event_type in RETENTION_SPECIAL_EVENTS:
            # Convert from friendly name to API value
            return_event_formatted = {"event_type": RETENTION_SPECIAL_EVENTS[return_event_type]}
        else:
            # Regular event name
            return_event_formatted = {"event_type": return_event_type}
        
        # Build params with proper retention mode handling
        params = {
            "se": start_event_formatted,
            "re": return_event_formatted,
            "start": start_date,
            "end": end_date
        }
        
        # Handle retention mode - only add 'rm' if not n_day (default)
        if retention_type in RETENTION_MODES:
            mode_value = RETENTION_MODES[retention_type]
            if mode_value is not None:  # Only add if not None (n_day is None)
                params["rm"] = mode_value
        elif retention_type and retention_type != "n_day":
            # If a custom retention type is provided, use it directly
            params["rm"] = retention_type
            
        # Add interval for N-day retention if specified
        if interval and retention_type == "n_day":
            params["i"] = interval
        
        return await self._make_request("retention", params, user_id, cost)
    
    async def get_realtime_active_users(self, user_id: str = "default") -> Dict[str, Any]:
        """Get real-time active users
        
        Args:
            user_id: User ID for rate limiting
            
        Returns:
            Real-time active user data
        """
        # Real-time endpoint has minimal cost
        cost = 1
        
        return await self._make_request("realtime", {}, user_id, cost)
    
    async def get_user_counts(
        self,
        start_date: str,
        end_date: str,
        metric: str = "active",
        interval: int = 1,
        segment_definitions: Optional[Dict[str, Any]] = None,
        group_by: Optional[str] = None,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Get active or new user counts
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            metric: Either "active" or "new" to get the desired count
            interval: Either 1, 7, or 30 for daily, weekly, and monthly counts
            segment_definitions: Optional segment definitions
            group_by: Optional property to group by
            user_id: User ID for rate limiting
            
        Returns:
            User count data
        """
        # Calculate cost: Base cost of 1 + 4 if group_by is used
        days = self._calculate_days(start_date, end_date)
        conditions = 1
        if segment_definitions:
            # Count number of conditions in segment definitions
            conditions = len(segment_definitions.get("filters", [{}]))
        base_cost = 1
        group_cost = 4 if group_by else 0
        cost = self.calculate_cost(days, conditions, base_cost + group_cost)
        
        # Build parameters for users API
        params = {
            "start": start_date,
            "end": end_date,
            "m": metric,
            "i": interval
        }
        
        if segment_definitions:
            params["s"] = segment_definitions
        if group_by:
            params["g"] = group_by
        
        return await self._make_request("users", params, user_id, cost)
    
    async def get_all_events(
        self,
        include_deleted: bool = False,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Get all event types using Taxonomy API
        
        Args:
            include_deleted: Whether to include deleted events
            user_id: User ID for rate limiting
            
        Returns:
            List of all event types in the project
        """
        # Taxonomy API has cost of 1 for GET requests
        cost = 1
        
        params = {}
        if include_deleted:
            params["showDeleted"] = "true"
        
        return await self._make_request("taxonomy/event", params, user_id, cost)

    async def get_events_list(
        self,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Get list of visible events with current week's totals using Events List API
        
        This is a simpler alternative to the Taxonomy API for basic event discovery.
        Returns events with current week's totals, uniques, and % DAU.
        Only visible events are returned (hidden events are excluded).
        
        Args:
            user_id: User ID for rate limiting
            
        Returns:
            List of visible events with current week's metrics
        """
        # Events List API has cost of 1 for GET requests
        cost = 1
        
        # No parameters needed for events/list endpoint
        return await self._make_request("events/list", {}, user_id, cost)