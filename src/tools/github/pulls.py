"""
GitHub pull requests operations for MCP Integration Hub
"""

from typing import Dict, Any, Optional
from .client import GitHubClient


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
        api_key: GitHub personal access token (optional)
    
    Returns:
        Dictionary containing list of pull requests
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
    
    if sort not in ["created", "updated", "popularity"]:
        return {
            "success": False,
            "error": "Sort must be 'created', 'updated', or 'popularity'"
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
    
    if head:
        params["head"] = head
    
    if base:
        params["base"] = base
    
    # Get pull requests
    prs_data = await client.get(f"/repos/{repo}/pulls", params)
    
    if "error" in prs_data:
        return {
            "success": False,
            "error": prs_data["error"]
        }
    
    # Limit results
    prs_data = prs_data[:limit]
    
    # Build response
    response = {
        "success": True,
        "total_count": len(prs_data),
        "repository": repo,
        "filters": {
            "state": state,
            "head": head,
            "base": base,
            "sort": sort,
            "direction": direction
        },
        "pull_requests": []
    }
    
    for pr in prs_data:
        pr_info = {
            "number": pr.get("number"),
            "title": pr.get("title"),
            "state": pr.get("state"),
            "body": pr.get("body"),
            "draft": pr.get("draft", False),
            "user": {
                "login": pr.get("user", {}).get("login"),
                "type": pr.get("user", {}).get("type")
            },
            "head": {
                "ref": pr.get("head", {}).get("ref"),
                "sha": pr.get("head", {}).get("sha"),
                "repo": pr.get("head", {}).get("repo", {}).get("full_name") if pr.get("head", {}).get("repo") else None
            },
            "base": {
                "ref": pr.get("base", {}).get("ref"),
                "sha": pr.get("base", {}).get("sha"),
                "repo": pr.get("base", {}).get("repo", {}).get("full_name") if pr.get("base", {}).get("repo") else None
            },
            "labels": [label.get("name") for label in pr.get("labels", [])],
            "assignees": [assignee.get("login") for assignee in pr.get("assignees", [])],
            "reviewers": [reviewer.get("login") for reviewer in pr.get("requested_reviewers", [])],
            "milestone": pr.get("milestone", {}).get("title") if pr.get("milestone") else None,
            "created_at": pr.get("created_at"),
            "updated_at": pr.get("updated_at"),
            "closed_at": pr.get("closed_at"),
            "merged_at": pr.get("merged_at"),
            "merge_commit_sha": pr.get("merge_commit_sha"),
            "mergeable": pr.get("mergeable"),
            "mergeable_state": pr.get("mergeable_state"),
            "merged": pr.get("merged", False),
            "comments": pr.get("comments", 0),
            "review_comments": pr.get("review_comments", 0),
            "commits": pr.get("commits", 0),
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
            "changed_files": pr.get("changed_files", 0),
            "urls": {
                "html": pr.get("html_url"),
                "api": pr.get("url"),
                "commits": pr.get("commits_url"),
                "comments": pr.get("comments_url"),
                "review_comments": pr.get("review_comments_url"),
                "diff": pr.get("diff_url"),
                "patch": pr.get("patch_url")
            }
        }
        response["pull_requests"].append(pr_info)
    
    return response 