"""Issue Handler - manages Gitea issues, labels, milestones, and comments"""

import json
from typing import Any

from plugins.gitea.client import GiteaClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === ISSUES ===
        {
            "name": "list_issues",
            "method_name": "list_issues",
            "description": "List issues in a Gitea repository with filters. Returns paginated list of issues.",
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
                    "labels": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated label IDs",
                    },
                    "q": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search query",
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
            "name": "get_issue",
            "method_name": "get_issue",
            "description": "Get details of a specific issue by number.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "issue_number": {
                        "type": "integer",
                        "description": "Issue number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "issue_number"],
            },
            "scope": "read",
        },
        {
            "name": "create_issue",
            "method_name": "create_issue",
            "description": "Create a new issue in a Gitea repository with optional labels, assignees, and milestone.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "title": {
                        "type": "string",
                        "description": "Issue title",
                        "minLength": 1,
                        "maxLength": 255,
                    },
                    "body": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Issue description (supports Markdown)",
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
                    "closed": {
                        "type": "boolean",
                        "description": "Create as closed",
                        "default": False,
                    },
                },
                "required": ["owner", "repo", "title"],
            },
            "scope": "write",
        },
        {
            "name": "update_issue",
            "method_name": "update_issue",
            "description": "Update an existing issue. Can modify title, body, state, assignees, labels, and milestone.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "issue_number": {
                        "type": "integer",
                        "description": "Issue number",
                        "minimum": 1,
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Issue title",
                    },
                    "body": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Issue description",
                    },
                    "state": {
                        "anyOf": [{"type": "string", "enum": ["open", "closed"]}, {"type": "null"}],
                        "description": "Issue state",
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
                "required": ["owner", "repo", "issue_number"],
            },
            "scope": "write",
        },
        {
            "name": "close_issue",
            "method_name": "close_issue",
            "description": "Close an issue.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "issue_number": {
                        "type": "integer",
                        "description": "Issue number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "issue_number"],
            },
            "scope": "write",
        },
        {
            "name": "reopen_issue",
            "method_name": "reopen_issue",
            "description": "Reopen a closed issue.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "issue_number": {
                        "type": "integer",
                        "description": "Issue number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "issue_number"],
            },
            "scope": "write",
        },
        # === COMMENTS ===
        {
            "name": "list_issue_comments",
            "method_name": "list_issue_comments",
            "description": "List all comments on an issue.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "issue_number": {
                        "type": "integer",
                        "description": "Issue number",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "issue_number"],
            },
            "scope": "read",
        },
        {
            "name": "create_issue_comment",
            "method_name": "create_issue_comment",
            "description": "Add a comment to an issue.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "issue_number": {
                        "type": "integer",
                        "description": "Issue number",
                        "minimum": 1,
                    },
                    "body": {
                        "type": "string",
                        "description": "Comment body (supports Markdown)",
                        "minLength": 1,
                    },
                },
                "required": ["owner", "repo", "issue_number", "body"],
            },
            "scope": "write",
        },
        # === LABELS ===
        {
            "name": "list_labels",
            "method_name": "list_labels",
            "description": "List all labels in a repository.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                },
                "required": ["owner", "repo"],
            },
            "scope": "read",
        },
        {
            "name": "create_label",
            "method_name": "create_label",
            "description": "Create a new label in a repository.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "name": {
                        "type": "string",
                        "description": "Label name",
                        "minLength": 1,
                        "maxLength": 50,
                    },
                    "color": {
                        "type": "string",
                        "description": "Label color (hex without #, e.g., 'ff0000')",
                        "pattern": "^[0-9A-Fa-f]{6}$",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Label description",
                        "maxLength": 200,
                    },
                },
                "required": ["owner", "repo", "name", "color"],
            },
            "scope": "write",
        },
        # === MILESTONES ===
        {
            "name": "list_milestones",
            "method_name": "list_milestones",
            "description": "List all milestones in a repository.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "state": {
                        "anyOf": [
                            {"type": "string", "enum": ["open", "closed", "all"]},
                            {"type": "null"},
                        ],
                        "description": "Filter by state",
                        "default": "open",
                    },
                },
                "required": ["owner", "repo"],
            },
            "scope": "read",
        },
        {
            "name": "create_milestone",
            "method_name": "create_milestone",
            "description": "Create a new milestone in a repository.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "title": {
                        "type": "string",
                        "description": "Milestone title",
                        "minLength": 1,
                        "maxLength": 255,
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Milestone description",
                    },
                    "due_on": {
                        "anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}],
                        "description": "Due date (ISO 8601 format)",
                    },
                    "state": {
                        "type": "string",
                        "description": "State",
                        "enum": ["open", "closed"],
                        "default": "open",
                    },
                },
                "required": ["owner", "repo", "title"],
            },
            "scope": "write",
        },
    ]

async def list_issues(
    client: GiteaClient,
    owner: str,
    repo: str,
    state: str = "open",
    labels: str | None = None,
    q: str | None = None,
    page: int = 1,
    limit: int = 30,
) -> str:
    """List repository issues"""
    params = {"state": state, "labels": labels, "q": q, "page": page, "limit": limit}
    issues = await client.list_issues(owner, repo, params)
    result = {"success": True, "count": len(issues), "issues": issues}
    return json.dumps(result, indent=2)

async def get_issue(client: GiteaClient, owner: str, repo: str, issue_number: int) -> str:
    """Get issue details"""
    issue = await client.get_issue(owner, repo, issue_number)
    result = {"success": True, "issue": issue}
    return json.dumps(result, indent=2)

async def create_issue(
    client: GiteaClient,
    owner: str,
    repo: str,
    title: str,
    body: str | None = None,
    assignee: str | None = None,
    assignees: list[str] | None = None,
    labels: list[int] | None = None,
    milestone: int | None = None,
    closed: bool = False,
) -> str:
    """Create a new issue"""
    data = {
        "title": title,
        "body": body,
        "assignee": assignee,
        "assignees": assignees,
        "labels": labels,
        "milestone": milestone,
        "closed": closed,
    }
    issue = await client.create_issue(owner, repo, data)
    result = {
        "success": True,
        "message": f"Issue #{issue['number']} created successfully",
        "issue": issue,
    }
    return json.dumps(result, indent=2)

async def update_issue(
    client: GiteaClient, owner: str, repo: str, issue_number: int, **kwargs
) -> str:
    """Update an issue"""
    # Build update data from kwargs
    data = {
        k: v
        for k, v in kwargs.items()
        if v is not None and k not in ["owner", "repo", "issue_number"]
    }

    issue = await client.update_issue(owner, repo, issue_number, data)
    result = {
        "success": True,
        "message": f"Issue #{issue_number} updated successfully",
        "issue": issue,
    }
    return json.dumps(result, indent=2)

async def close_issue(client: GiteaClient, owner: str, repo: str, issue_number: int) -> str:
    """Close an issue"""
    data = {"state": "closed"}
    issue = await client.update_issue(owner, repo, issue_number, data)
    result = {
        "success": True,
        "message": f"Issue #{issue_number} closed successfully",
        "issue": issue,
    }
    return json.dumps(result, indent=2)

async def reopen_issue(client: GiteaClient, owner: str, repo: str, issue_number: int) -> str:
    """Reopen an issue"""
    data = {"state": "open"}
    issue = await client.update_issue(owner, repo, issue_number, data)
    result = {
        "success": True,
        "message": f"Issue #{issue_number} reopened successfully",
        "issue": issue,
    }
    return json.dumps(result, indent=2)

# Comment operations
async def list_issue_comments(client: GiteaClient, owner: str, repo: str, issue_number: int) -> str:
    """List issue comments"""
    comments = await client.list_issue_comments(owner, repo, issue_number)
    result = {"success": True, "count": len(comments), "comments": comments}
    return json.dumps(result, indent=2)

async def create_issue_comment(
    client: GiteaClient, owner: str, repo: str, issue_number: int, body: str
) -> str:
    """Create issue comment"""
    data = {"body": body}
    comment = await client.create_issue_comment(owner, repo, issue_number, data)
    result = {
        "success": True,
        "message": f"Comment added to issue #{issue_number}",
        "comment": comment,
    }
    return json.dumps(result, indent=2)

# Label operations
async def list_labels(client: GiteaClient, owner: str, repo: str) -> str:
    """List repository labels"""
    labels = await client.list_labels(owner, repo)
    result = {"success": True, "count": len(labels), "labels": labels}
    return json.dumps(result, indent=2)

async def create_label(
    client: GiteaClient,
    owner: str,
    repo: str,
    name: str,
    color: str,
    description: str | None = None,
) -> str:
    """Create a label"""
    data = {"name": name, "color": color, "description": description}
    label = await client.create_label(owner, repo, data)
    result = {"success": True, "message": f"Label '{name}' created successfully", "label": label}
    return json.dumps(result, indent=2)

# Milestone operations
async def list_milestones(
    client: GiteaClient, owner: str, repo: str, state: str | None = None
) -> str:
    """List repository milestones"""
    milestones = await client.list_milestones(owner, repo, state=state)
    result = {"success": True, "count": len(milestones), "milestones": milestones}
    return json.dumps(result, indent=2)

async def create_milestone(
    client: GiteaClient,
    owner: str,
    repo: str,
    title: str,
    description: str | None = None,
    due_on: str | None = None,
    state: str = "open",
) -> str:
    """Create a milestone"""
    data = {"title": title, "description": description, "due_on": due_on, "state": state}
    milestone = await client.create_milestone(owner, repo, data)
    result = {
        "success": True,
        "message": f"Milestone '{title}' created successfully",
        "milestone": milestone,
    }
    return json.dumps(result, indent=2)
