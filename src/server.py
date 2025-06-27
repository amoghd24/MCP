# server.py
"""
MCP Integration Hub Server
Provides tools for Notion, Slack, and GitHub integrations
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from typing import Optional, Dict, Any
import json

# Import our modules
from src.config.settings import settings
from src.tools.notion_tool import NotionClient, extract_title, simplify_properties, parse_blocks_to_text
from src.auth.middleware import AuthManager

# Create an MCP server
mcp = FastMCP(
    name=settings.server_name,
    host=settings.server_host,
    port=settings.server_port
)

# Initialize auth manager
auth_manager = AuthManager(settings.encryption_key)


# Simple tool (calculator) - keeping for testing
@mcp.tool()
def calculator(a: int, b: int) -> int:
    """Calculate the sum of two numbers"""
    return a + b


# ============= NOTION TOOLS =============

@mcp.tool()  # Cache for 1 minute
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
    notion_api_key = api_key or settings.notion_api_key or os.getenv("NOTION_API_KEY")
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


@mcp.tool()
async def read_notion_page(
    page_id: str,
    api_key: Optional[str] = None,
    include_content: bool = True
) -> Dict[str, Any]:
    """
    Read a specific Notion page and optionally its content
    
    Args:
        page_id: The ID of the Notion page
        api_key: Notion API key (optional if set in environment)
        include_content: Whether to include page blocks/content (default: True)
    
    Returns:
        Page metadata and content
    """
    notion_api_key = api_key or settings.notion_api_key or os.getenv("NOTION_API_KEY")
    if not notion_api_key:
        return {"error": "No API key provided"}
    
    
    client = NotionClient(notion_api_key)
    try:
        # Get page metadata
        page_data = await client.get_page(page_id)
        
        result = {
            "id": page_data["id"],
            "title": extract_title(page_data),
            "url": page_data.get("url", ""),
            "properties": simplify_properties(page_data.get("properties", {})),
            "created_time": page_data.get("created_time", ""),
            "last_edited_time": page_data.get("last_edited_time", "")
        }
        
        # Optionally get page content
        if include_content:
            blocks = await client.get_page_content(page_id)
            result["content"] = parse_blocks_to_text(blocks)
        
        return result
    except Exception as e:
        return {"error": f"Failed to read page: {str(e)}"}
    finally:
        await client.close()


@mcp.tool()
async def query_notion_database(
    database_id: str,
    filter_json: Optional[str] = None,  # JSON string for complex filters
    property_filter: Optional[str] = None,  # Simple property=value filter
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Query a Notion database with optional filters
    
    Args:
        database_id: The ID of the Notion database
        filter_json: Complex filter as JSON string (follows Notion API format)
        property_filter: Simple filter format like "Status=Done" 
        api_key: Notion API key (optional if set in environment)
    
    Returns:
        Database query results
    """
    notion_api_key = api_key or settings.notion_api_key or os.getenv("NOTION_API_KEY")
    if not notion_api_key:
        return {"error": "No API key provided"}
    
    # Check rate limit
    if not api_rate_limiter.check_api_limit("notion", "default"):
        wait_time = api_rate_limiter.wait_if_limited("notion", "default")
        return {"error": f"Rate limit exceeded. Please wait {wait_time:.1f} seconds"}
    
    client = NotionClient(notion_api_key)
    try:
        # Parse filters
        filter_dict = None
        if filter_json:
            filter_dict = json.loads(filter_json)
        elif property_filter and "=" in property_filter:
            # Convert simple filter to Notion format
            prop, value = property_filter.split("=", 1)
            filter_dict = {
                "property": prop.strip(),
                "select": {"equals": value.strip()}
            }
        
        results = await client.query_database(database_id, filter_dict)
        
        # Simplify results
        simplified_results = []
        for item in results.get("results", []):
            simplified_results.append({
                "id": item["id"],
                "title": extract_title(item),
                "properties": simplify_properties(item.get("properties", {})),
                "url": item.get("url", ""),
                "created_time": item.get("created_time", "")
            })
        
        return {
            "results": simplified_results,
            "count": len(simplified_results),
            "has_more": results.get("has_more", False)
        }
    except Exception as e:
        return {"error": f"Failed to query database: {str(e)}"}
    finally:
        await client.close()


# ============= SLACK TOOLS (Placeholder) =============

@mcp.tool()
async def read_slack(
    channel: str,
    limit: int = 100,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Read messages from a Slack channel (placeholder)
    
    Args:
        channel: Channel name or ID
        limit: Number of messages to retrieve
        api_key: Slack bot token
    
    Returns:
        Channel messages
    """
    return {"error": "Slack integration not yet implemented"}


# ============= GITHUB TOOLS (Placeholder) =============

@mcp.tool()
async def read_github(
    repo: str,
    resource_type: str = "issues",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Read data from GitHub repository (placeholder)
    
    Args:
        repo: Repository in format 'owner/repo'
        resource_type: Type of resource to read ('issues', 'prs', 'commits')
        api_key: GitHub personal access token
    
    Returns:
        GitHub data
    """
    return {"error": "GitHub integration not yet implemented"}


# ============= SERVER TOOLS =============

@mcp.tool()
def server_info() -> Dict[str, Any]:
    """Get information about this MCP server"""
    return {
        "name": settings.server_name,
        "version": "0.1.0",
        "tools": [
            {"name": "search_notion", "description": "Search Notion pages and databases"},
            {"name": "read_notion_page", "description": "Read a specific Notion page"},
            {"name": "query_notion_database", "description": "Query a Notion database"},
            {"name": "read_slack", "description": "Read Slack messages (coming soon)"},
            {"name": "read_github", "description": "Read GitHub data (coming soon)"},
        ],
        "transport": settings.transport,
        "rate_limits": {
            "notion": "180 requests/minute",
            "slack": "60 requests/minute",
            "github": "5000 requests/hour"
        }
    }


# Run the server
if __name__ == "__main__":
    print(f"Starting {settings.server_name}")
    print(f"Transport: {settings.transport}")
    print(f"Host: {settings.server_host}:{settings.server_port}")
    
    if settings.transport == "stdio":
        print("Starting MCP server on stdio")
        mcp.run(transport="stdio")
    elif settings.transport == "sse":
        print(f"Starting MCP server on SSE at http://{settings.server_host}:{settings.server_port}")
        try:
            mcp.run(transport="sse")
        except Exception as e:
            print(f"Error starting server: {e}")
    else:
        print(f"Invalid transport: {settings.transport}")
        exit(1)
        