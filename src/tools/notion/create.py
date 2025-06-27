"""
Create Notion Page Tool
Tool for creating new pages in Notion
"""

from typing import Optional, Dict, Any
import os
from .client import NotionClient, create_text_block, parse_markdown_to_blocks


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
    notion_api_key = api_key or os.getenv("NOTION_API_KEY")
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