"""
Slack Channels Tools
Tools for reading channel messages and getting channel information
"""

from typing import Optional, Dict, List, Any
import os
from .client import SlackClient
from .utils import resolve_channel_id, format_message_data, parse_message_text


async def read_slack_channel(
    channel: str,
    limit: int = 100,
    include_threads: bool = True,
    oldest: Optional[str] = None,
    latest: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Read messages from a Slack channel
    
    Args:
        channel: Channel name or ID
        limit: Number of messages to retrieve (will paginate if > 100)
        include_threads: Whether to include thread replies
        oldest: Only messages after this timestamp
        latest: Only messages before this timestamp
        api_key: Slack bot token
    
    Returns:
        Dict with messages array and channel info
    """
    slack_token = api_key or os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        return {"error": "No API key provided. Please provide api_key or set SLACK_BOT_TOKEN environment variable"}
    
    client = SlackClient(slack_token)
    try:
        # Resolve channel ID
        try:
            channel_id = await resolve_channel_id(client, channel)
        except ValueError:
            channel_id = channel
        
        # Get channel info first
        channel_info_response = await client.conversations_info(channel_id)
        if not channel_info_response.get("ok"):
            error = channel_info_response.get("error", "Unknown error")
            if error == "channel_not_found":
                return {"error": f"Channel '{channel}' not found"}
            elif error == "not_in_channel":
                return {"error": f"Bot must be added to channel '{channel}' to read messages"}
            return {"error": f"Failed to get channel info: {error}"}
        
        channel_info = channel_info_response.get("channel", {})
        
        # Fetch messages with pagination
        all_messages = []
        cursor = None
        remaining = limit
        
        while remaining > 0:
            batch_size = min(remaining, 100)  # Slack's max limit per request
            
            response = await client.conversations_history(
                channel=channel_id,
                cursor=cursor,
                limit=batch_size,
                oldest=oldest,
                latest=latest
            )
            
            if not response.get("ok"):
                error = response.get("error", "Unknown error")
                if error == "not_in_channel":
                    return {"error": f"Bot must be added to channel '{channel}' to read messages"}
                return {"error": f"Failed to fetch messages: {error}"}
            
            messages = response.get("messages", [])
            all_messages.extend(messages)
            
            # Check if we need to continue pagination
            cursor = response.get("response_metadata", {}).get("next_cursor")
            remaining -= len(messages)
            
            if not cursor or not response.get("has_more", False):
                break
        
        # Format messages
        formatted_messages = []
        for message in all_messages[:limit]:  # Ensure we don't exceed requested limit
            formatted_msg = format_message_data(message)
            formatted_msg["parsed_text"] = parse_message_text(formatted_msg["text"])
            
            # Fetch thread replies if requested and message has replies
            if include_threads and message.get("thread_ts") and message.get("reply_count", 0) > 0:
                thread_response = await client.conversations_replies(
                    channel=channel_id,
                    ts=message["thread_ts"]
                )
                
                if thread_response.get("ok"):
                    replies = thread_response.get("messages", [])[1:]  # Skip the parent message
                    formatted_msg["thread_replies"] = [
                        {
                            **format_message_data(reply),
                            "parsed_text": parse_message_text(reply.get("text", ""))
                        }
                        for reply in replies
                    ]
            
            formatted_messages.append(formatted_msg)
        
        return {
            "success": True,
            "channel": {
                "id": channel_info.get("id"),
                "name": channel_info.get("name"),
                "is_private": channel_info.get("is_private", False),
                "topic": channel_info.get("topic", {}).get("value", ""),
                "purpose": channel_info.get("purpose", {}).get("value", "")
            },
            "messages": formatted_messages,
            "message_count": len(formatted_messages),
            "has_more": bool(cursor),
            "oldest": oldest,
            "latest": latest
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read channel: {str(e)}"
        }
    finally:
        await client.close()


async def get_slack_channel_info(
    channel_name: str,
    include_members: bool = False,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a Slack channel
    
    Args:
        channel_name: Name of the channel to find
        include_members: Whether to include member list
        api_key: Slack bot token
    
    Returns:
        Dict with channel metadata (id, name, topic, purpose, member_count, etc.)
    """
    slack_token = api_key or os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        return {"error": "No API key provided. Please provide api_key or set SLACK_BOT_TOKEN environment variable"}
    
    client = SlackClient(slack_token)
    try:
        # Remove # if present
        clean_channel_name = channel_name.lstrip('#')
        
        # Search for channel by name
        found_channel = None
        cursor = None
        
        while True:
            response = await client.conversations_list(cursor=cursor)
            
            if not response.get("ok"):
                return {"error": f"Failed to list channels: {response.get('error')}"}
            
            for channel in response.get("channels", []):
                if channel["name"] == clean_channel_name:
                    found_channel = channel
                    break
            
            if found_channel:
                break
            
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        
        if not found_channel:
            return {
                "success": False,
                "error": f"Channel '{channel_name}' not found"
            }
        
        # Get detailed channel info
        info_response = await client.conversations_info(found_channel["id"])
        if not info_response.get("ok"):
            return {"error": f"Failed to get channel details: {info_response.get('error')}"}
        
        channel_details = info_response.get("channel", {})
        
        # Prepare response
        result = {
            "success": True,
            "channel": {
                "id": channel_details.get("id"),
                "name": channel_details.get("name"),
                "name_normalized": channel_details.get("name_normalized"),
                "is_channel": channel_details.get("is_channel", False),
                "is_private": channel_details.get("is_private", False),
                "is_archived": channel_details.get("is_archived", False),
                "is_general": channel_details.get("is_general", False),
                "creator": channel_details.get("creator"),
                "created": channel_details.get("created"),
                "topic": {
                    "value": channel_details.get("topic", {}).get("value", ""),
                    "creator": channel_details.get("topic", {}).get("creator"),
                    "last_set": channel_details.get("topic", {}).get("last_set")
                },
                "purpose": {
                    "value": channel_details.get("purpose", {}).get("value", ""),
                    "creator": channel_details.get("purpose", {}).get("creator"),
                    "last_set": channel_details.get("purpose", {}).get("last_set")
                },
                "num_members": channel_details.get("num_members", 0)
            }
        }
        
        # Optionally include member list
        if include_members and result["channel"]["num_members"] > 0:
            members = []
            cursor = None
            
            while True:
                members_response = await client.conversations_members(
                    channel=found_channel["id"],
                    cursor=cursor
                )
                
                if members_response.get("ok"):
                    members.extend(members_response.get("members", []))
                    cursor = members_response.get("response_metadata", {}).get("next_cursor")
                    if not cursor:
                        break
                else:
                    # Don't fail the whole request if we can't get members
                    result["members_error"] = members_response.get("error")
                    break
            
            result["members"] = members
            result["member_count"] = len(members)
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get channel info: {str(e)}"
        }
    finally:
        await client.close() 