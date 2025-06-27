"""
Notion Tool for MCP Server
Provides integration with Notion API for searching, reading pages, and querying databases
"""

from typing import Optional, Dict, List, Any, Union
import httpx
from datetime import datetime
import json
import os


class NotionClient:
    """Wrapper for Notion API operations"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"  # Latest stable version
        }
        self.client = httpx.AsyncClient(headers=self.headers)
    
    async def search(self, query: str, filter_type: Optional[str] = None) -> Dict:
        """Search across all pages and databases"""
        payload = {"query": query}
        if filter_type:
            payload["filter"] = {"value": filter_type, "property": "object"}
        
        response = await self.client.post(
            f"{self.base_url}/search",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    async def get_page(self, page_id: str) -> Dict:
        """Retrieve a specific page"""
        response = await self.client.get(f"{self.base_url}/pages/{page_id}")
        response.raise_for_status()
        return response.json()
    
    async def get_page_content(self, page_id: str) -> List[Dict]:
        """Retrieve all blocks (content) from a page"""
        blocks = []
        has_more = True
        start_cursor = None
        
        while has_more:
            url = f"{self.base_url}/blocks/{page_id}/children"
            params = {}
            if start_cursor:
                params["start_cursor"] = start_cursor
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            blocks.extend(data.get("results", []))
            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")
        
        return blocks
    
    async def query_database(self, database_id: str, filter_dict: Optional[Dict] = None, 
                           sorts: Optional[List[Dict]] = None) -> Dict:
        """Query a database with optional filters and sorts"""
        payload = {}
        if filter_dict:
            payload["filter"] = filter_dict
        if sorts:
            payload["sorts"] = sorts
        
        response = await self.client.post(
            f"{self.base_url}/databases/{database_id}/query",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Helper functions for processing Notion data
def extract_title(notion_object: Dict) -> str:
    """Extract title from various Notion object types"""
    # For pages with properties
    if "properties" in notion_object:
        for prop in notion_object["properties"].values():
            if prop.get("type") == "title" and prop.get("title"):
                return "".join([t.get("plain_text", "") for t in prop["title"]])
    
    # For database/page results from search
    if "title" in notion_object:
        if isinstance(notion_object["title"], list):
            return "".join([t.get("plain_text", "") for t in notion_object["title"]])
    
    return "Untitled"


def simplify_properties(properties: Dict) -> Dict:
    """Convert Notion properties to simple key-value pairs"""
    simple = {}
    for key, prop in properties.items():
        prop_type = prop.get("type")
        
        if prop_type == "title" and prop.get("title"):
            simple[key] = "".join([t.get("plain_text", "") for t in prop["title"]])
        elif prop_type == "rich_text" and prop.get("rich_text"):
            simple[key] = "".join([t.get("plain_text", "") for t in prop["rich_text"]])
        elif prop_type == "select" and prop.get("select"):
            simple[key] = prop["select"].get("name", "")
        elif prop_type == "multi_select" and prop.get("multi_select"):
            simple[key] = [s.get("name", "") for s in prop["multi_select"]]
        elif prop_type == "number":
            simple[key] = prop.get("number")
        elif prop_type == "checkbox":
            simple[key] = prop.get("checkbox", False)
        elif prop_type == "date" and prop.get("date"):
            simple[key] = prop["date"].get("start", "")
        elif prop_type == "url":
            simple[key] = prop.get("url", "")
        elif prop_type == "email":
            simple[key] = prop.get("email", "")
        elif prop_type == "phone_number":
            simple[key] = prop.get("phone_number", "")
        
    return simple


def parse_blocks_to_text(blocks: List[Dict]) -> str:
    """Convert Notion blocks to readable text"""
    text_parts = []
    
    for block in blocks:
        block_type = block.get("type")
        
        if block_type == "paragraph" and block.get("paragraph", {}).get("rich_text"):
            text = "".join([t.get("plain_text", "") for t in block["paragraph"]["rich_text"]])
            if text:
                text_parts.append(text)
        
        elif block_type == "heading_1" and block.get("heading_1", {}).get("rich_text"):
            text = "# " + "".join([t.get("plain_text", "") for t in block["heading_1"]["rich_text"]])
            text_parts.append(text)
        
        elif block_type == "heading_2" and block.get("heading_2", {}).get("rich_text"):
            text = "## " + "".join([t.get("plain_text", "") for t in block["heading_2"]["rich_text"]])
            text_parts.append(text)
        
        elif block_type == "heading_3" and block.get("heading_3", {}).get("rich_text"):
            text = "### " + "".join([t.get("plain_text", "") for t in block["heading_3"]["rich_text"]])
            text_parts.append(text)
        
        elif block_type == "bulleted_list_item" and block.get("bulleted_list_item", {}).get("rich_text"):
            text = "• " + "".join([t.get("plain_text", "") for t in block["bulleted_list_item"]["rich_text"]])
            text_parts.append(text)
        
        elif block_type == "numbered_list_item" and block.get("numbered_list_item", {}).get("rich_text"):
            text = "1. " + "".join([t.get("plain_text", "") for t in block["numbered_list_item"]["rich_text"]])
            text_parts.append(text)
        
        elif block_type == "code" and block.get("code", {}).get("rich_text"):
            code = "".join([t.get("plain_text", "") for t in block["code"]["rich_text"]])
            lang = block["code"].get("language", "")
            text_parts.append(f"```{lang}\n{code}\n```")
        
        elif block_type == "divider":
            text_parts.append("---")
    
    return "\n\n".join(text_parts) 