"""
GitHub issues operations for MCP Integration Hub
"""

from typing import Dict, Any, Optional, List
from .client import GitHubClient


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
        api_key: GitHub personal access token (optional)
    
    Returns:
        Dictionary containing list of issues
    """
    # Validate repo format
    if '/' not in repo:
        return {
            "success": False,
            "error": "Invalid repository format. Use 'owner/repo'"
        }
    
    # Validate parameters
    if state not in ["open", "closed", "all"]:
        return {
            "success": False,
            "error": "State must be 'open', 'closed', or 'all'"
        }
    
    if sort not in ["created", "updated", "comments"]:
        return {
            "success": False,
            "error": "Sort must be 'created', 'updated', or 'comments'"
        }
    
    if direction not in ["asc", "desc"]:
        return {
            "success": False,
            "error": "Direction must be 'asc' or 'desc'"
        }
    
    client = GitHubClient(api_key)
    
    # Build query parameters
    params = {
        "state": state,
        "sort": sort,
        "direction": direction,
        "per_page": min(limit, 100)  # GitHub API max is 100 per page
    }
    
    if labels:
        params["labels"] = ",".join(labels)
    
    if assignee:
        params["assignee"] = assignee
    
    # Get issues
    issues_data = await client.get(f"/repos/{repo}/issues", params)
    
    if "error" in issues_data:
        return {
            "success": False,
            "error": issues_data["error"]
        }
    
    # Filter out pull requests (GitHub includes PRs in issues endpoint)
    issues = [issue for issue in issues_data if "pull_request" not in issue][:limit]
    
    # Build response
    response = {
        "success": True,
        "total_count": len(issues),
        "repository": repo,
        "filters": {
            "state": state,
            "labels": labels,
            "assignee": assignee,
            "sort": sort,
            "direction": direction
        },
        "issues": []
    }
    
    for issue in issues:
        issue_info = {
            "number": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "body": issue.get("body"),
            "user": {
                "login": issue.get("user", {}).get("login"),
                "type": issue.get("user", {}).get("type")
            },
            "labels": [label.get("name") for label in issue.get("labels", [])],
            "assignees": [assignee.get("login") for assignee in issue.get("assignees", [])],
            "milestone": issue.get("milestone", {}).get("title") if issue.get("milestone") else None,
            "comments": issue.get("comments", 0),
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
            "closed_at": issue.get("closed_at"),
            "urls": {
                "html": issue.get("html_url"),
                "api": issue.get("url"),
                "comments": issue.get("comments_url")
            }
        }
        response["issues"].append(issue_info)
    
    return response 