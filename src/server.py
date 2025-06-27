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

# Import our modules
from src.config.settings import settings
from src.auth.middleware import AuthManager

# Import Notion tools from the new modular structure
from src.tools.notion.search import search_notion as notion_search
from src.tools.notion.read import read_notion_page as notion_read_page
from src.tools.notion.create import create_notion_page as notion_create_page
from src.tools.notion.content import add_notion_content as notion_add_content

# Create an MCP server
mcp = FastMCP(
    name=settings.server_name,
    host=settings.server_host,
    port=settings.server_port
)

# Initialize auth manager
auth_manager = AuthManager(settings.encryption_key)


# ============= NOTION TOOLS =============

@mcp.tool()
async def search_notion(
    query: str,
    api_key: Optional[str] = None,
    filter_type: Optional[str] = None
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
    # Add settings API key if not provided
    if not api_key:
        api_key = settings.notion_api_key
    return await notion_search(query, api_key, filter_type)


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
    if not api_key:
        api_key = settings.notion_api_key
    return await notion_read_page(page_id, api_key, include_content)


@mcp.tool()
async def create_notion_page(
    parent_page_id: str,
    title: str,
    content: Optional[str] = None,
    content_format: str = "markdown",
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
    if not api_key:
        api_key = settings.notion_api_key
    return await notion_create_page(parent_page_id, title, content, content_format, api_key)


@mcp.tool()
async def add_notion_content(
    page_id: str,
    content: str,
    content_format: str = "markdown",
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
    if not api_key:
        api_key = settings.notion_api_key
    return await notion_add_content(page_id, content, content_format, api_key)


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
        