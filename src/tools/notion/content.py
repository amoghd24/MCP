"""
Add Notion Content Tool
Tool for adding content to existing Notion pages
"""

from typing import Optional, Dict, Any
import os
from .client import NotionClient, create_text_block, parse_markdown_to_blocks


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
    notion_api_key = api_key or os.getenv("NOTION_API_KEY")
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