"""
Amplitude Analytics API Client
Handles authentication, rate limiting, and API communication
"""

import base64
import json
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.utils.rate_limiter import api_rate_limiter


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
            response = await self.client.get(url, params=params)
            
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
                return {
                    "error": f"API request failed",
                    "status_code": response.status_code,
                    "message": response.text
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
        retention_type: str = "retention_N_day",
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Get retention analysis data
        
        Args:
            start_event: Starting event definition
            return_event: Return event definition
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            retention_type: Type of retention analysis
            user_id: User ID for rate limiting
            
        Returns:
            Retention analysis data
        """
        # Calculate cost: Fixed cost of 8
        days = self._calculate_days(start_date, end_date)
        cost = self.calculate_cost(days, 1, 8)
        
        # Format events for retention analysis
        start_event_param = json.dumps({"event_type": start_event["event_type"]})
        return_event_param = json.dumps({"event_type": return_event["event_type"]})
        
        params = {
            "se": start_event_param,
            "re": return_event_param,
            "start": start_date,
            "end": end_date,
            "rm": retention_type
        }
        
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