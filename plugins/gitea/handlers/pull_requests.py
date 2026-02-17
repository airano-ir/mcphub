"""Pull Request Handler - manages Gitea pull requests, reviews, and merges"""

import json
from typing import Any

from plugins.gitea.client import GiteaClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === PULL REQUESTS ===
        {
            "name": "list_pull_requests",
            "method_name": "list_pull_requests",
            "description": "List pull requests in a Gitea repository with filters.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "state": {
                        "type": "string",
                        "description": "Filter by state",
                        "enum": ["open", "closed", "all"],
                        "default": "open",
                    },
                    "sort": {
                        "type": "string",
                        "description": "Sort by",
                        "enum": ["created", "updated", "comments", "recentupdate"],
                        "default": "created",
                    },
                    "labels": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated label IDs",
                    },
                    "milestone": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Milestone name",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number",
                        "default": 1,
                        "minimum": 1,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Items per page (1-100)",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["owner", "repo"],
            },
            "scope": "read",
        },
        {
            "name": "get_pull_request",
            "method_name": "get_pull_request",
            "description": "Get details of a specific pull request by number.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "pr_number"],
            },
            "scope": "read",
        },
        {
            "name": "create_pull_request",
            "method_name": "create_pull_request",
            "description": "Create a new pull request in a Gitea repository.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "title": {
                        "type": "string",
                        "description": "Pull request title",
                        "minLength": 1,
                        "maxLength": 255,
                    },
                    "head": {
                        "type": "string",
                        "description": "Source branch (head branch)",
                        "minLength": 1,
                    },
                    "base": {
                        "type": "string",
                        "description": "Target branch (base branch)",
                        "minLength": 1,
                    },
                    "body": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Pull request description (supports Markdown)",
                    },
                    "assignee": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Assignee username",
                    },
                    "assignees": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "List of assignee usernames",
                    },
                    "labels": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "List of label IDs",
                    },
                    "milestone": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Milestone ID",
                    },
                },
                "required": ["owner", "repo", "title", "head", "base"],
            },
            "scope": "write",
        },
        {
            "name": "update_pull_request",
            "method_name": "update_pull_request",
            "description": "Update an existing pull request. Can modify title, body, state, assignees, labels, and milestone.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Pull request title",
                    },
                    "body": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Pull request description",
                    },
                    "state": {
                        "anyOf": [{"type": "string", "enum": ["open", "closed"]}, {"type": "null"}],
                        "description": "Pull request state",
                    },
                    "assignee": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Assignee username",
                    },
                    "assignees": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "List of assignee usernames",
                    },
                    "labels": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "integer"}},
                            {"type": "null"},
                        ],
                        "description": "List of label IDs",
                    },
                    "milestone": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Milestone ID",
                    },
                },
                "required": ["owner", "repo", "pr_number"],
            },
            "scope": "write",
        },
        {
            "name": "merge_pull_request",
            "method_name": "merge_pull_request",
            "description": "Merge a pull request using specified merge method.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                    "method": {
                        "type": "string",
                        "description": "Merge method",
                        "enum": ["merge", "rebase", "rebase-merge", "squash"],
                        "default": "merge",
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Merge commit title",
                    },
                    "message": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Merge commit message",
                    },
                    "delete_branch_after_merge": {
                        "type": "boolean",
                        "description": "Delete source branch after merge",
                        "default": False,
                    },
                },
                "required": ["owner", "repo", "pr_number"],
            },
            "scope": "write",
        },
        {
            "name": "close_pull_request",
            "method_name": "close_pull_request",
            "description": "Close a pull request without merging.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "pr_number"],
            },
            "scope": "write",
        },
        {
            "name": "reopen_pull_request",
            "method_name": "reopen_pull_request",
            "description": "Reopen a closed pull request.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "pr_number"],
            },
            "scope": "write",
        },
        # === PR DETAILS ===
        {
            "name": "list_pr_commits",
            "method_name": "list_pr_commits",
            "description": "List all commits in a pull request.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "pr_number"],
            },
            "scope": "read",
        },
        {
            "name": "list_pr_files",
            "method_name": "list_pr_files",
            "description": "List all changed files in a pull request with additions/deletions count.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "pr_number"],
            },
            "scope": "read",
        },
        {
            "name": "get_pr_diff",
            "method_name": "get_pr_diff",
            "description": "Get the unified diff of a pull request.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "pr_number"],
            },
            "scope": "read",
        },
        {
            "name": "list_pr_comments",
            "method_name": "list_pr_comments",
            "description": "List all comments on a pull request.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "pr_number"],
            },
            "scope": "read",
        },
        {
            "name": "create_pr_comment",
            "method_name": "create_pr_comment",
            "description": "Add a comment to a pull request.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                    "body": {
                        "type": "string",
                        "description": "Comment body (supports Markdown)",
                        "minLength": 1,
                    },
                },
                "required": ["owner", "repo", "pr_number", "body"],
            },
            "scope": "write",
        },
        # === PR REVIEWS ===
        {
            "name": "list_pr_reviews",
            "method_name": "list_pr_reviews",
            "description": "List all reviews on a pull request.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "pr_number"],
            },
            "scope": "read",
        },
        {
            "name": "create_pr_review",
            "method_name": "create_pr_review",
            "description": "Create a review for a pull request (approve, request changes, or comment).",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                    "event": {
                        "type": "string",
                        "description": "Review event type",
                        "enum": ["APPROVED", "REQUEST_CHANGES", "COMMENT"],
                    },
                    "body": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Review comment (optional for APPROVED)",
                    },
                },
                "required": ["owner", "repo", "pr_number", "event"],
            },
            "scope": "write",
        },
        {
            "name": "request_pr_reviewers",
            "method_name": "request_pr_reviewers",
            "description": "Request reviewers for a pull request.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number",
                        "minimum": 1,
                    },
                    "reviewers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of reviewer usernames",
                        "minItems": 1,
                    },
                },
                "required": ["owner", "repo", "pr_number", "reviewers"],
            },
            "scope": "write",
        },
    ]

async def list_pull_requests(
    client: GiteaClient,
    owner: str,
    repo: str,
    state: str = "open",
    sort: str = "created",
    labels: str | None = None,
    milestone: str | None = None,
    page: int = 1,
    limit: int = 30,
) -> str:
    """List repository pull requests"""
    params = {
        "state": state,
        "sort": sort,
        "labels": labels,
        "milestone": milestone,
        "page": page,
        "limit": limit,
    }
    prs = await client.list_pull_requests(owner, repo, params)
    result = {"success": True, "count": len(prs), "pull_requests": prs}
    return json.dumps(result, indent=2)

async def get_pull_request(client: GiteaClient, owner: str, repo: str, pr_number: int) -> str:
    """Get pull request details"""
    pr = await client.get_pull_request(owner, repo, pr_number)
    result = {"success": True, "pull_request": pr}
    return json.dumps(result, indent=2)

async def create_pull_request(
    client: GiteaClient,
    owner: str,
    repo: str,
    title: str,
    head: str,
    base: str,
    body: str | None = None,
    assignee: str | None = None,
    assignees: list[str] | None = None,
    labels: list[int] | None = None,
    milestone: int | None = None,
) -> str:
    """Create a new pull request"""
    data = {
        "title": title,
        "head": head,
        "base": base,
        "body": body,
        "assignee": assignee,
        "assignees": assignees,
        "labels": labels,
        "milestone": milestone,
    }
    pr = await client.create_pull_request(owner, repo, data)
    result = {
        "success": True,
        "message": f"Pull request #{pr['number']} created successfully",
        "pull_request": pr,
    }
    return json.dumps(result, indent=2)

async def update_pull_request(
    client: GiteaClient, owner: str, repo: str, pr_number: int, **kwargs
) -> str:
    """Update a pull request"""
    # Build update data from kwargs
    data = {
        k: v for k, v in kwargs.items() if v is not None and k not in ["owner", "repo", "pr_number"]
    }

    pr = await client.update_pull_request(owner, repo, pr_number, data)
    result = {
        "success": True,
        "message": f"Pull request #{pr_number} updated successfully",
        "pull_request": pr,
    }
    return json.dumps(result, indent=2)

async def merge_pull_request(
    client: GiteaClient,
    owner: str,
    repo: str,
    pr_number: int,
    method: str = "merge",
    title: str | None = None,
    message: str | None = None,
    delete_branch_after_merge: bool = False,
) -> str:
    """Merge a pull request"""
    data = {
        "Do": method,
        "MergeTitleField": title,
        "MergeMessageField": message,
        "delete_branch_after_merge": delete_branch_after_merge,
    }
    merge_result = await client.merge_pull_request(owner, repo, pr_number, data)
    result = {
        "success": True,
        "message": f"Pull request #{pr_number} merged successfully using {method}",
        "result": merge_result,
    }
    return json.dumps(result, indent=2)

async def close_pull_request(client: GiteaClient, owner: str, repo: str, pr_number: int) -> str:
    """Close a pull request"""
    data = {"state": "closed"}
    pr = await client.update_pull_request(owner, repo, pr_number, data)
    result = {
        "success": True,
        "message": f"Pull request #{pr_number} closed successfully",
        "pull_request": pr,
    }
    return json.dumps(result, indent=2)

async def reopen_pull_request(client: GiteaClient, owner: str, repo: str, pr_number: int) -> str:
    """Reopen a pull request"""
    data = {"state": "open"}
    pr = await client.update_pull_request(owner, repo, pr_number, data)
    result = {
        "success": True,
        "message": f"Pull request #{pr_number} reopened successfully",
        "pull_request": pr,
    }
    return json.dumps(result, indent=2)

# PR Details
async def list_pr_commits(client: GiteaClient, owner: str, repo: str, pr_number: int) -> str:
    """List pull request commits"""
    commits = await client.list_pr_commits(owner, repo, pr_number)
    result = {"success": True, "count": len(commits), "commits": commits}
    return json.dumps(result, indent=2)

async def list_pr_files(client: GiteaClient, owner: str, repo: str, pr_number: int) -> str:
    """List pull request files"""
    files = await client.list_pr_files(owner, repo, pr_number)
    result = {"success": True, "count": len(files), "files": files}
    return json.dumps(result, indent=2)

async def get_pr_diff(client: GiteaClient, owner: str, repo: str, pr_number: int) -> str:
    """Get pull request diff"""
    diff = await client.get_pr_diff(owner, repo, pr_number)
    result = {"success": True, "diff": diff}
    return json.dumps(result, indent=2)

async def list_pr_comments(client: GiteaClient, owner: str, repo: str, pr_number: int) -> str:
    """List pull request comments"""
    # PR comments are same as issue comments in Gitea API
    comments = await client.list_issue_comments(owner, repo, pr_number)
    result = {"success": True, "count": len(comments), "comments": comments}
    return json.dumps(result, indent=2)

async def create_pr_comment(
    client: GiteaClient, owner: str, repo: str, pr_number: int, body: str
) -> str:
    """Create pull request comment"""
    data = {"body": body}
    comment = await client.create_issue_comment(owner, repo, pr_number, data)
    result = {
        "success": True,
        "message": f"Comment added to pull request #{pr_number}",
        "comment": comment,
    }
    return json.dumps(result, indent=2)

# PR Reviews
async def list_pr_reviews(client: GiteaClient, owner: str, repo: str, pr_number: int) -> str:
    """List pull request reviews"""
    reviews = await client.list_pr_reviews(owner, repo, pr_number)
    result = {"success": True, "count": len(reviews), "reviews": reviews}
    return json.dumps(result, indent=2)

async def create_pr_review(
    client: GiteaClient, owner: str, repo: str, pr_number: int, event: str, body: str | None = None
) -> str:
    """Create pull request review"""
    data = {"event": event, "body": body}
    review = await client.create_pr_review(owner, repo, pr_number, data)
    result = {
        "success": True,
        "message": f"Review {event} added to pull request #{pr_number}",
        "review": review,
    }
    return json.dumps(result, indent=2)

async def request_pr_reviewers(
    client: GiteaClient, owner: str, repo: str, pr_number: int, reviewers: list[str]
) -> str:
    """Request pull request reviewers"""
    data = {"reviewers": reviewers}
    reviewers_result = await client.request_pr_reviewers(owner, repo, pr_number, data)
    result = {
        "success": True,
        "message": f"Reviewers requested for pull request #{pr_number}",
        "result": reviewers_result,
    }
    return json.dumps(result, indent=2)
