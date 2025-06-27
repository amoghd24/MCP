"""
GitHub API client for MCP Integration Hub
"""

import aiohttp
from typing import Dict, Any, Optional
import asyncio


class GitHubClient:
    """Simple GitHub API client"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MCP-Integration-Hub"
        }
        if api_key:
            self.headers["Authorization"] = f"token {api_key}"
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request to GitHub API"""
        url = f"{self.base_url}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        return {"error": "Repository or resource not found"}
                    elif response.status == 401:
                        return {"error": "Authentication failed. Please check your API key"}
                    elif response.status == 403:
                        return {"error": "Access forbidden. You may have hit the rate limit"}
                    else:
                        return {"error": f"GitHub API error: {response.status}"}
            except aiohttp.ClientError as e:
                return {"error": f"Network error: {str(e)}"}
            except Exception as e:
                return {"error": f"Unexpected error: {str(e)}"} 