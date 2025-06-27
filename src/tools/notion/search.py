"""
Search Notion Tool
Tool for searching pages and databases in Notion
"""

from typing import Optional, Dict, Any
import os
from mcp.server.fastmcp import FastMCP
from .client import NotionClient, extract_title


async def search_notion(
    query: str,
    api_key: Optional[str] = None,
    filter_type: Optional[str] = None  # "page" or "database"
) -> Dict[str, Any]:
    """
    Search for pages and databases in Notion
    
    Args:
        query: Search query string
        api_key: Notion API key (optional if set in environment)
        filter_type: Filter results by type - 'page' or 'database' (optional)
    
    Returns:
        Search results from Notion
    """
    # Use provided API key or fall back to environment variable
    notion_api_key = api_key or os.getenv("NOTION_API_KEY")
    if not notion_api_key:
        return {"error": "No API key provided. Set NOTION_API_KEY env var or pass api_key parameter"}
    
    client = NotionClient(notion_api_key)
    try:
        results = await client.search(query, filter_type)
        
        # Process and simplify results
        simplified_results = []
        for item in results.get("results", []):
            simplified_item = {
                "id": item["id"],
                "type": item["object"],
                "title": extract_title(item),
                "url": item.get("url", ""),
                "last_edited": item.get("last_edited_time", "")
            }
            simplified_results.append(simplified_item)
        
        return {
            "results": simplified_results,
            "count": len(simplified_results),
            "has_more": results.get("has_more", False)
        }
    except Exception as e:
        return {"error": f"Failed to search Notion: {str(e)}"}
    finally:
        await client.close() 