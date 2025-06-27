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
from src.tools.notion_tool import (
    NotionClient, extract_title, simplify_properties, parse_blocks_to_text,
    create_text_block, create_heading_block, create_bullet_list_item,
    create_numbered_list_item, create_code_block, create_divider_block,
    parse_markdown_to_blocks
)
from src.auth.middleware import AuthManager

# Create an MCP server
mcp = FastMCP(
    name=settings.server_name,
    host=settings.server_host,
    port=settings.server_port
)

# Initialize auth manager
auth_manager = AuthManager(settings.encryption_key)


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
async def create_notion_page(
    parent_page_id: str,
    title: str,
    content: Optional[str] = None,
    content_format: str = "markdown",  # "markdown" or "plain"
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new Notion page
    
    Args:
        parent_page_id: ID of the parent page where this page will be created
        title: Title of the new page
        content: Optional content for the page
        content_format: Format of content - 'markdown' or 'plain' (default: markdown)
        api_key: Notion API key (optional if set in environment)
    
    Returns:
        Created page information
    """
    notion_api_key = api_key or settings.notion_api_key or os.getenv("NOTION_API_KEY")
    if not notion_api_key:
        return {"error": "No API key provided"}
    
    client = NotionClient(notion_api_key)
    try:
        # Prepare parent object
        parent = {"page_id": parent_page_id}
        
        # Prepare properties (title)
        properties = {
            "title": {
                "title": [{"text": {"content": title}}]
            }
        }
        
        # Prepare content blocks if provided
        children = None
        if content:
            if content_format == "markdown":
                children = parse_markdown_to_blocks(content)
            else:
                # Plain text - just create paragraph blocks
                children = [create_text_block(line) for line in content.split('\n') if line.strip()]
        
        # Create the page
        result = await client.create_page(parent, properties, children)
        
        return {
            "id": result["id"],
            "url": result.get("url", ""),
            "title": title,
            "created_time": result.get("created_time", ""),
            "success": True
        }
    except Exception as e:
        return {"error": f"Failed to create page: {str(e)}"}
    finally:
        await client.close()


@mcp.tool()
async def add_notion_content(
    page_id: str,
    content: str,
    content_format: str = "markdown",  # "markdown" or "plain"
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add content to an existing Notion page
    
    Args:
        page_id: ID of the page to add content to
        content: Content to add
        content_format: Format of content - 'markdown' or 'plain' (default: markdown)
        api_key: Notion API key (optional if set in environment)
    
    Returns:
        Success status and block information
    """
    notion_api_key = api_key or settings.notion_api_key or os.getenv("NOTION_API_KEY")
    if not notion_api_key:
        return {"error": "No API key provided"}
    
    client = NotionClient(notion_api_key)
    try:
        # Parse content into blocks
        if content_format == "markdown":
            blocks = parse_markdown_to_blocks(content)
        else:
            # Plain text - create paragraph blocks
            blocks = [create_text_block(line) for line in content.split('\n') if line.strip()]
        
        if not blocks:
            return {"error": "No content to add"}
        
        # Append blocks to the page
        result = await client.append_blocks(page_id, blocks)
        
        return {
            "success": True,
            "blocks_added": len(result.get("results", [])),
            "page_id": page_id
        }
    except Exception as e:
        return {"error": f"Failed to add content: {str(e)}"}
    finally:
        await client.close()


@mcp.tool()
async def create_notion_database(
    parent_page_id: str,
    title: str,
    properties_schema: Dict[str, str],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new Notion database
    
    Args:
        parent_page_id: ID of the parent page where database will be created
        title: Title of the database
        properties_schema: Schema definition as {"PropertyName": "type"} 
                          where type is: "title", "text", "number", "select", "multi_select", 
                          "checkbox", "date", "url", "email", "phone"
        api_key: Notion API key (optional if set in environment)
    
    Returns:
        Created database information
    """
    notion_api_key = api_key or settings.notion_api_key or os.getenv("NOTION_API_KEY")
    if not notion_api_key:
        return {"error": "No API key provided"}
    
    client = NotionClient(notion_api_key)
    try:
        # Prepare parent
        parent = {"page_id": parent_page_id}
        
        # Prepare title
        title_rich_text = [{"text": {"content": title}}]
        
        # Convert simple schema to Notion property format
        properties = {}
        
        # Ensure there's at least one title property
        has_title = False
        for prop_name, prop_type in properties_schema.items():
            if prop_type == "title":
                properties[prop_name] = {"title": {}}
                has_title = True
            elif prop_type == "text":
                properties[prop_name] = {"rich_text": {}}
            elif prop_type == "number":
                properties[prop_name] = {"number": {"format": "number"}}
            elif prop_type == "checkbox":
                properties[prop_name] = {"checkbox": {}}
            elif prop_type == "select":
                properties[prop_name] = {"select": {"options": []}}
            elif prop_type == "multi_select":
                properties[prop_name] = {"multi_select": {"options": []}}
            elif prop_type == "date":
                properties[prop_name] = {"date": {}}
            elif prop_type == "url":
                properties[prop_name] = {"url": {}}
            elif prop_type == "email":
                properties[prop_name] = {"email": {}}
            elif prop_type == "phone":
                properties[prop_name] = {"phone_number": {}}
        
        # If no title property, add a default one
        if not has_title:
            properties["Name"] = {"title": {}}
        
        # Create the database
        result = await client.create_database(parent, title_rich_text, properties)
        
        return {
            "id": result["id"],
            "url": result.get("url", ""),
            "title": title,
            "created_time": result.get("created_time", ""),
            "properties": list(properties.keys()),
            "success": True
        }
    except Exception as e:
        return {"error": f"Failed to create database: {str(e)}"}
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
        