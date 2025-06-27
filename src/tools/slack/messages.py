"""
Slack Messages Tool
Tool for sending messages to Slack
"""

from typing import Optional, Dict, List, Any
import os
from .client import SlackClient
from .utils import resolve_channel_id, markdown_to_blocks


async def send_slack_message(
    channel: str,
    text: str,
    blocks: Optional[List[Dict]] = None,
    thread_ts: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send a message to a Slack channel
    
    Args:
        channel: Channel name (with or without #) or channel ID
        text: Plain text message (fallback for blocks)
        blocks: Block Kit formatted message blocks
        thread_ts: Thread timestamp to reply to
        api_key: Slack bot token
    
    Returns:
        Dict with success status, message ts, and channel
    """
    slack_token = api_key or os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        return {"error": "No API key provided. Please provide api_key or set SLACK_BOT_TOKEN environment variable"}
    
    client = SlackClient(slack_token)
    try:
        # Resolve channel ID if channel is a name
        try:
            channel_id = await resolve_channel_id(client, channel)
        except ValueError as e:
            # If channel resolution fails, try using the channel as-is
            # (it might be a valid ID we don't recognize)
            channel_id = channel
        
        # If blocks not provided but text contains markdown, convert it
        if not blocks and text and any(marker in text for marker in ['#', '*', '```', '-', '1.']):
            blocks = markdown_to_blocks(text)
        
        # Send message
        result = await client.post_message(
            channel=channel_id,
            text=text,
            blocks=blocks,
            thread_ts=thread_ts
        )
        
        if result.get("ok"):
            return {
                "success": True,
                "message_ts": result.get("ts"),
                "channel": result.get("channel"),
                "thread_ts": thread_ts,
                "message": "Message sent successfully"
            }
        else:
            error = result.get("error", "Unknown error")
            error_msg = f"Failed to send message: {error}"
            
            # Provide helpful error messages
            if error == "channel_not_found":
                error_msg = f"Channel '{channel}' not found or bot doesn't have access"
            elif error == "not_in_channel":
                error_msg = f"Bot must be added to channel '{channel}' first"
            elif error == "invalid_auth":
                error_msg = "Invalid authentication token"
            elif error == "missing_scope":
                error_msg = "Bot token missing required scope: chat:write"
            
            return {
                "success": False,
                "error": error_msg,
                "slack_error": error
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send message: {str(e)}"
        }
    finally:
        await client.close() 