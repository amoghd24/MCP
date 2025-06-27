"""
Slack Utility Functions
Helper functions for Slack operations
"""

from typing import Optional, Dict, List, Any
from .client import SlackClient


async def resolve_channel_id(client: SlackClient, channel: str) -> str:
    """
    Convert channel name to ID if needed
    
    Args:
        client: SlackClient instance
        channel: Channel name (with or without #) or channel ID
    
    Returns:
        Channel ID
    """
    # If already an ID (starts with C or D), return it
    if channel.startswith(('C', 'D', 'G')):
        return channel
    
    # Remove # prefix if present
    channel_name = channel.lstrip('#')
    
    # Search for channel using conversations.list
    cursor = None
    while True:
        response = await client.conversations_list(cursor=cursor)
        
        if not response.get("ok"):
            raise ValueError(f"Failed to list channels: {response.get('error')}")
        
        for ch in response.get("channels", []):
            if ch["name"] == channel_name:
                return ch["id"]
        
        # Check if there are more channels to search
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    
    raise ValueError(f"Channel '{channel_name}' not found")


# Block Kit builder functions
def create_section_block(text: str, block_id: Optional[str] = None, 
                        fields: Optional[List[Dict]] = None) -> Dict:
    """Create a section block"""
    block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": text
        }
    }
    
    if block_id:
        block["block_id"] = block_id
    
    if fields:
        block["fields"] = fields
    
    return block


def create_header_block(text: str, block_id: Optional[str] = None) -> Dict:
    """Create a header block"""
    block = {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": text,
            "emoji": True
        }
    }
    
    if block_id:
        block["block_id"] = block_id
    
    return block


def create_divider_block() -> Dict:
    """Create a divider block"""
    return {"type": "divider"}


def create_context_block(elements: List[str]) -> Dict:
    """Create a context block with text elements"""
    return {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": text
            } for text in elements
        ]
    }


def markdown_to_blocks(markdown: str) -> List[Dict]:
    """
    Convert markdown text to Slack Block Kit blocks
    Basic implementation for common markdown patterns
    """
    blocks = []
    lines = markdown.split('\n')
    current_list_items = []
    
    for i, line in enumerate(lines):
        # Skip empty lines
        if not line.strip():
            # If we were building a list, add it as a section
            if current_list_items:
                blocks.append(create_section_block('\n'.join(current_list_items)))
                current_list_items = []
            continue
        
        # Headers
        if line.startswith('# '):
            # Flush any pending list
            if current_list_items:
                blocks.append(create_section_block('\n'.join(current_list_items)))
                current_list_items = []
            blocks.append(create_header_block(line[2:]))
        
        elif line.startswith('## ') or line.startswith('### '):
            # Flush any pending list
            if current_list_items:
                blocks.append(create_section_block('\n'.join(current_list_items)))
                current_list_items = []
            # Convert to bold text in section
            text = line.lstrip('#').strip()
            blocks.append(create_section_block(f"*{text}*"))
        
        # Lists
        elif line.startswith(('- ', '* ', '• ')):
            # Add to current list
            item_text = line[2:].strip()
            current_list_items.append(f"• {item_text}")
        
        elif line[0].isdigit() and '. ' in line[:4]:
            # Numbered list
            parts = line.split('. ', 1)
            if len(parts) == 2:
                current_list_items.append(f"{parts[0]}. {parts[1]}")
        
        # Divider
        elif line.strip() in ['---', '***', '___']:
            # Flush any pending list
            if current_list_items:
                blocks.append(create_section_block('\n'.join(current_list_items)))
                current_list_items = []
            blocks.append(create_divider_block())
        
        # Code block
        elif line.startswith('```'):
            # Flush any pending list
            if current_list_items:
                blocks.append(create_section_block('\n'.join(current_list_items)))
                current_list_items = []
            
            # Find the end of code block
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                code_lines.append(lines[i])
                i += 1
            
            code_text = '\n'.join(code_lines)
            blocks.append(create_section_block(f"```{code_text}```"))
        
        # Regular text
        else:
            # Flush any pending list
            if current_list_items:
                blocks.append(create_section_block('\n'.join(current_list_items)))
                current_list_items = []
            blocks.append(create_section_block(line))
    
    # Don't forget any remaining list items
    if current_list_items:
        blocks.append(create_section_block('\n'.join(current_list_items)))
    
    return blocks


def format_message_data(message: Dict, include_user: bool = True) -> Dict:
    """
    Format raw Slack message into clean structure
    
    Args:
        message: Raw message from Slack API
        include_user: Whether to include user information
    
    Returns:
        Formatted message dict
    """
    formatted = {
        "text": message.get("text", ""),
        "ts": message.get("ts", ""),
        "type": message.get("type", ""),
        "thread_ts": message.get("thread_ts")
    }
    
    if include_user:
        formatted["user"] = message.get("user", "")
        formatted["username"] = message.get("username")
    
    # Include thread info if present
    if "reply_count" in message:
        formatted["thread_info"] = {
            "reply_count": message.get("reply_count", 0),
            "reply_users_count": message.get("reply_users_count", 0),
            "latest_reply": message.get("latest_reply"),
            "subscribed": message.get("subscribed", False)
        }
    
    # Include reactions if present
    if "reactions" in message:
        formatted["reactions"] = [
            {
                "name": r.get("name"),
                "count": r.get("count"),
                "users": r.get("users", [])
            }
            for r in message.get("reactions", [])
        ]
    
    # Include attachments if present
    if "attachments" in message:
        formatted["attachments"] = message["attachments"]
    
    # Include blocks if present
    if "blocks" in message:
        formatted["blocks"] = message["blocks"]
    
    return formatted


def parse_message_text(text: str) -> str:
    """
    Parse Slack's mrkdwn format to more readable text
    This is a basic implementation
    """
    # Convert user mentions <@U123456> to @user
    import re
    text = re.sub(r'<@(U\w+)>', r'@\1', text)
    
    # Convert channel mentions <#C123456|channel> to #channel
    text = re.sub(r'<#C\w+\|([^>]+)>', r'#\1', text)
    
    # Convert links <http://example.com|Example> to Example (http://example.com)
    text = re.sub(r'<(https?://[^|>]+)\|([^>]+)>', r'\2 (\1)', text)
    
    # Convert plain links <http://example.com> to http://example.com
    text = re.sub(r'<(https?://[^>]+)>', r'\1', text)
    
    return text 