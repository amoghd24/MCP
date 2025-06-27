"""
Read Notion Page Tool
Tool for reading specific Notion pages and their content
"""

from typing import Optional, Dict, Any
import os
from .client import NotionClient, extract_title, simplify_properties, parse_blocks_to_text


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
    notion_api_key = api_key or os.getenv("NOTION_API_KEY")
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