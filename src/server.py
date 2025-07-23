# server.py
"""
MCP Integration Hub Server
Provides tools for Notion, Slack, and GitHub integrations
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from typing import Optional, Dict, Any, List

# Import our modules
from src.config.settings import settings
from src.auth.middleware import AuthManager

# Import Notion tools from the new modular structure
from src.tools.notion.search import search_notion as notion_search
from src.tools.notion.read import read_notion_page as notion_read_page
from src.tools.notion.create import create_notion_page as notion_create_page
from src.tools.notion.content import add_notion_content as notion_add_content

# Import Slack tools
from src.tools.slack.messages import send_slack_message as slack_send_message
from src.tools.slack.channels import (
    read_slack_channel as slack_read_channel,
    get_slack_channel_info as slack_channel_info
)

# Import GitHub tools
from src.tools.github.repos import read_github_repo as github_read_repo
from src.tools.github.issues import read_github_issues as github_read_issues
from src.tools.github.pulls import read_github_prs as github_read_prs

# Import Amplitude tools
from src.tools.amplitude.retention import (
    get_amplitude_retention as amplitude_retention
)
from src.tools.amplitude.users import (
    get_amplitude_users as amplitude_users
)
from src.tools.amplitude.get_events import (
    get_amplitude_events_list as amplitude_events_list,
    get_amplitude_event_details as amplitude_event_details
)

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


# ============= SLACK TOOLS =============

@mcp.tool()
async def send_slack_message(
    channel: str,
    text: str,
    blocks: Optional[List[Dict]] = None,
    thread_ts: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send a message to a Slack channel with Block Kit support
    
    Args:
        channel: Channel name (with or without #) or channel ID
        text: Plain text message (fallback for blocks)
        blocks: Block Kit formatted message blocks
        thread_ts: Thread timestamp to reply to
        api_key: Slack bot token (optional if set in environment)
    
    Returns:
        Dict with success status, message timestamp, and channel
    """
    if not api_key:
        api_key = settings.slack_bot_token
    return await slack_send_message(channel, text, blocks, thread_ts, api_key)


@mcp.tool()
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
        oldest: Only messages after this timestamp (Unix timestamp or Slack timestamp)
        latest: Only messages before this timestamp (Unix timestamp or Slack timestamp)
        api_key: Slack bot token (optional if set in environment)
    
    Returns:
        Dict with messages array and channel info
    """
    if not api_key:
        api_key = settings.slack_bot_token
    return await slack_read_channel(channel, limit, include_threads, oldest, latest, api_key)


@mcp.tool()
async def get_slack_channel_info(
    channel_name: str,
    include_members: bool = False,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a Slack channel
    
    Args:
        channel_name: Name of the channel to find (with or without #)
        include_members: Whether to include member list
        api_key: Slack bot token (optional if set in environment)
    
    Returns:
        Dict with channel metadata (id, name, topic, purpose, member_count, etc.)
    """
    if not api_key:
        api_key = settings.slack_bot_token
    return await slack_channel_info(channel_name, include_members, api_key)


# ============= GITHUB TOOLS =============

@mcp.tool()
async def read_github_repo(
    repo: str,
    include_stats: bool = True,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get repository metadata, statistics, and configuration
    
    Args:
        repo: Repository in 'owner/repo' format
        include_stats: Whether to include statistics like stars, forks
        api_key: GitHub personal access token (optional if set in environment)
    
    Returns:
        Repository information including metadata, stats, and URLs
    """
    if not api_key:
        api_key = settings.github_token
    return await github_read_repo(repo, include_stats, api_key)


@mcp.tool()
async def read_github_issues(
    repo: str,
    state: str = "open",
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    sort: str = "created",
    direction: str = "desc",
    limit: int = 30,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    List repository issues with filtering options
    
    Args:
        repo: Repository in 'owner/repo' format
        state: Issue state - 'open', 'closed', or 'all'
        labels: List of label names to filter by
        assignee: Username to filter by assignee
        sort: Sort by 'created', 'updated', or 'comments'
        direction: Sort direction - 'asc' or 'desc'
        limit: Maximum number of issues to return
        api_key: GitHub personal access token (optional if set in environment)
    
    Returns:
        List of issues with metadata, labels, assignees, and timestamps
    """
    if not api_key:
        api_key = settings.github_token
    return await github_read_issues(repo, state, labels, assignee, sort, direction, limit, api_key)


@mcp.tool()
async def read_github_prs(
    repo: str,
    state: str = "open",
    head: Optional[str] = None,
    base: Optional[str] = None,
    sort: str = "created",
    direction: str = "desc",
    limit: int = 30,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    List repository pull requests with filtering options
    
    Args:
        repo: Repository in 'owner/repo' format
        state: PR state - 'open', 'closed', or 'all'
        head: Filter by head branch (format: 'user:branch')
        base: Filter by base branch
        sort: Sort by 'created', 'updated', or 'popularity' (comment count)
        direction: Sort direction - 'asc' or 'desc'
        limit: Maximum number of PRs to return
        api_key: GitHub personal access token (optional if set in environment)
    
    Returns:
        List of pull requests with metadata, merge status, and review information
    """
    if not api_key:
        api_key = settings.github_token
    return await github_read_prs(repo, state, head, base, sort, direction, limit, api_key)


# ============= AMPLITUDE TOOLS =============

@mcp.tool()
async def get_amplitude_retention(
    start_event: str,
    return_event: str,
    start_date: str,
    end_date: str,
    retention_type: str = "n_day",
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get retention analysis data from Amplitude Dashboard API
    
    Args:
        start_event: Initial event that defines the cohort
        return_event: Event that defines user return/retention
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        retention_type: Type of retention analysis ("n_day", "rolling", "bracket", or "unbounded")
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Retention analysis with cohort data and retention curves
    """
    if not api_key:
        api_key = settings.amplitude_api_key
    if not secret_key:
        secret_key = settings.amplitude_secret_key
    return await amplitude_retention(start_event, return_event, start_date, end_date, retention_type, None, api_key, secret_key)


@mcp.tool()
async def get_amplitude_users(
    start_date: str,
    end_date: str,
    metric: str = "active",
    interval: int = 1,
    segment_definitions: Optional[Dict[str, Any]] = None,
    group_by: Optional[str] = None,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get active or new user counts from Amplitude Dashboard API
    
    Args:
        start_date: Start date in YYYYMMDD format (e.g., "20240101")
        end_date: End date in YYYYMMDD format (e.g., "20240131")
        metric: Either "active" or "new" to get the desired count. Defaults to "active"
        interval: Either 1, 7, or 30 for daily, weekly, and monthly counts, respectively. Defaults to 1
        segment_definitions: Optional segment definitions to filter users
        group_by: Optional property to group by (e.g., "city", "country")
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Dictionary containing user count data with formatted summary
    """
    if not api_key:
        api_key = settings.amplitude_api_key
    if not secret_key:
        secret_key = settings.amplitude_secret_key
    return await amplitude_users(start_date, end_date, metric, interval, segment_definitions, group_by, api_key, secret_key)




@mcp.tool()
async def get_amplitude_events_list(
    include_deleted: bool = False,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a complete list of all event types in the Amplitude project
    
    Args:
        include_deleted: Whether to include deleted/inactive events (default: False)
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Complete list of event names and metadata for discovery and analysis
    """
    if not api_key:
        api_key = settings.amplitude_api_key
    if not secret_key:
        secret_key = settings.amplitude_secret_key
    return await amplitude_events_list(include_deleted, api_key, secret_key)


@mcp.tool()
async def get_amplitude_event_details(
    event_name: str,
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed information about a specific Amplitude event
    
    Args:
        event_name: Name of the event to get details for
        api_key: Amplitude API key (optional if set in environment)
        secret_key: Amplitude secret key (optional if set in environment)
    
    Returns:
        Detailed event information including properties, description, and category
    """
    if not api_key:
        api_key = settings.amplitude_api_key
    if not secret_key:
        secret_key = settings.amplitude_secret_key
    return await amplitude_event_details(event_name, api_key, secret_key)


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
        