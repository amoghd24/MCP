"""
Slack Client Module
Core client for interacting with Slack API
"""

from typing import Optional, Dict, List, Any
import httpx
import json


class SlackClient:
    """Wrapper for Slack API operations"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://slack.com/api"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        self.client = httpx.AsyncClient(headers=self.headers)
    
    async def post_message(self, channel: str, text: str, 
                          blocks: Optional[List[Dict]] = None,
                          thread_ts: Optional[str] = None) -> Dict:
        """Send a message using chat.postMessage"""
        payload = {
            "channel": channel,
            "text": text
        }
        
        if blocks:
            payload["blocks"] = blocks
        
        if thread_ts:
            payload["thread_ts"] = thread_ts
        
        response = await self.client.post(
            f"{self.base_url}/chat.postMessage",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    async def conversations_list(self, cursor: Optional[str] = None,
                               limit: int = 100,
                               types: str = "public_channel,private_channel") -> Dict:
        """List conversations in workspace"""
        params = {
            "limit": limit,
            "types": types
        }
        
        if cursor:
            params["cursor"] = cursor
        
        response = await self.client.get(
            f"{self.base_url}/conversations.list",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def conversations_history(self, channel: str,
                                  cursor: Optional[str] = None,
                                  limit: int = 100,
                                  oldest: Optional[str] = None,
                                  latest: Optional[str] = None) -> Dict:
        """Get conversation history"""
        params = {
            "channel": channel,
            "limit": limit
        }
        
        if cursor:
            params["cursor"] = cursor
        if oldest:
            params["oldest"] = oldest
        if latest:
            params["latest"] = latest
        
        response = await self.client.get(
            f"{self.base_url}/conversations.history",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def conversations_info(self, channel: str) -> Dict:
        """Get channel information"""
        params = {"channel": channel}
        
        response = await self.client.get(
            f"{self.base_url}/conversations.info",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def conversations_members(self, channel: str,
                                  cursor: Optional[str] = None,
                                  limit: int = 100) -> Dict:
        """Get channel members"""
        params = {
            "channel": channel,
            "limit": limit
        }
        
        if cursor:
            params["cursor"] = cursor
        
        response = await self.client.get(
            f"{self.base_url}/conversations.members",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def conversations_replies(self, channel: str, ts: str,
                                  cursor: Optional[str] = None,
                                  limit: int = 100) -> Dict:
        """Get thread replies"""
        params = {
            "channel": channel,
            "ts": ts,
            "limit": limit
        }
        
        if cursor:
            params["cursor"] = cursor
        
        response = await self.client.get(
            f"{self.base_url}/conversations.replies",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def users_info(self, user: str) -> Dict:
        """Get user information"""
        params = {"user": user}
        
        response = await self.client.get(
            f"{self.base_url}/users.info",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose() 