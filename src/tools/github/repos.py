"""
GitHub repository operations for MCP Integration Hub
"""

from typing import Dict, Any, Optional
from .client import GitHubClient


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
        api_key: GitHub personal access token (optional)
    
    Returns:
        Dictionary containing repository information
    """
    # Validate repo format
    if '/' not in repo:
        return {
            "success": False,
            "error": "Invalid repository format. Use 'owner/repo'"
        }
    
    client = GitHubClient(api_key)
    
    # Get repository data
    repo_data = await client.get(f"/repos/{repo}")
    
    if "error" in repo_data:
        return {
            "success": False,
            "error": repo_data["error"]
        }
    
    # Build response
    response = {
        "success": True,
        "repository": {
            "name": repo_data.get("name"),
            "full_name": repo_data.get("full_name"),
            "description": repo_data.get("description"),
            "private": repo_data.get("private", False),
            "owner": {
                "login": repo_data.get("owner", {}).get("login"),
                "type": repo_data.get("owner", {}).get("type")
            },
            "default_branch": repo_data.get("default_branch"),
            "language": repo_data.get("language"),
            "topics": repo_data.get("topics", []),
            "homepage": repo_data.get("homepage"),
            "created_at": repo_data.get("created_at"),
            "updated_at": repo_data.get("updated_at"),
            "pushed_at": repo_data.get("pushed_at"),
            "urls": {
                "html": repo_data.get("html_url"),
                "api": repo_data.get("url"),
                "clone": repo_data.get("clone_url"),
                "ssh": repo_data.get("ssh_url")
            }
        }
    }
    
    # Add stats if requested
    if include_stats:
        response["repository"]["stats"] = {
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "watchers": repo_data.get("watchers_count", 0),
            "open_issues": repo_data.get("open_issues_count", 0),
            "size": repo_data.get("size", 0),
            "subscribers": repo_data.get("subscribers_count", 0)
        }
    
    return response 