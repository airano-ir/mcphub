"""User & Organization Handler - manages Gitea users, organizations, and teams"""

import json
from typing import Any

from plugins.gitea.client import GiteaClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === USERS ===
        {
            "name": "get_user",
            "method_name": "get_user",
            "description": "Get information about a Gitea user by username.",
            "schema": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username to look up",
                        "minLength": 1,
                    }
                },
                "required": ["username"],
            },
            "scope": "read",
        },
        {
            "name": "list_user_repos",
            "method_name": "list_user_repos",
            "description": "List all public repositories of a Gitea user.",
            "schema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username", "minLength": 1},
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
                "required": ["username"],
            },
            "scope": "read",
        },
        {
            "name": "search_users",
            "method_name": "search_users",
            "description": "Search for Gitea users by query or user ID.",
            "schema": {
                "type": "object",
                "properties": {
                    "q": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search query (username or full name)",
                    },
                    "uid": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "User ID to search for",
                    },
                },
            },
            "scope": "read",
        },
        # === ORGANIZATIONS ===
        {
            "name": "list_organizations",
            "method_name": "list_organizations",
            "description": "List organizations for the current authenticated user.",
            "schema": {
                "type": "object",
                "properties": {
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
            },
            "scope": "read",
        },
        {
            "name": "get_organization",
            "method_name": "get_organization",
            "description": "Get information about a Gitea organization by name.",
            "schema": {
                "type": "object",
                "properties": {
                    "org": {"type": "string", "description": "Organization name", "minLength": 1}
                },
                "required": ["org"],
            },
            "scope": "read",
        },
        {
            "name": "list_org_repos",
            "method_name": "list_org_repos",
            "description": "List all repositories of an organization.",
            "schema": {
                "type": "object",
                "properties": {
                    "org": {"type": "string", "description": "Organization name", "minLength": 1},
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
                "required": ["org"],
            },
            "scope": "read",
        },
        # === TEAMS ===
        {
            "name": "list_org_teams",
            "method_name": "list_org_teams",
            "description": "List all teams in an organization.",
            "schema": {
                "type": "object",
                "properties": {
                    "org": {"type": "string", "description": "Organization name", "minLength": 1},
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
                "required": ["org"],
            },
            "scope": "read",
        },
        {
            "name": "list_team_members",
            "method_name": "list_team_members",
            "description": "List all members of a team.",
            "schema": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "integer", "description": "Team ID", "minimum": 1},
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
                "required": ["team_id"],
            },
            "scope": "read",
        },
    ]


async def get_user(client: GiteaClient, username: str) -> str:
    """Get user information"""
    user = await client.get_user(username)
    result = {"success": True, "user": user}
    return json.dumps(result, indent=2)


async def list_user_repos(
    client: GiteaClient, username: str, page: int = 1, limit: int = 30
) -> str:
    """List user repositories"""
    repos = await client.list_user_repos(username, page=page, limit=limit)
    result = {"success": True, "count": len(repos), "repositories": repos}
    return json.dumps(result, indent=2)


async def search_users(client: GiteaClient, q: str | None = None, uid: int | None = None) -> str:
    """Search users"""
    users = await client.search_users(query=q, uid=uid)
    result = {"success": True, "count": len(users), "users": users}
    return json.dumps(result, indent=2)


# Organization operations
async def list_organizations(client: GiteaClient, page: int = 1, limit: int = 30) -> str:
    """List organizations"""
    orgs = await client.list_organizations(page=page, limit=limit)
    result = {"success": True, "count": len(orgs), "organizations": orgs}
    return json.dumps(result, indent=2)


async def get_organization(client: GiteaClient, org: str) -> str:
    """Get organization information"""
    organization = await client.get_organization(org)
    result = {"success": True, "organization": organization}
    return json.dumps(result, indent=2)


async def list_org_repos(client: GiteaClient, org: str, page: int = 1, limit: int = 30) -> str:
    """List organization repositories"""
    repos = await client.list_org_repos(org, page=page, limit=limit)
    result = {"success": True, "count": len(repos), "repositories": repos}
    return json.dumps(result, indent=2)


# Team operations
async def list_org_teams(client: GiteaClient, org: str, page: int = 1, limit: int = 30) -> str:
    """List organization teams"""
    teams = await client.list_org_teams(org, page=page, limit=limit)
    result = {"success": True, "count": len(teams), "teams": teams}
    return json.dumps(result, indent=2)


async def list_team_members(
    client: GiteaClient, team_id: int, page: int = 1, limit: int = 30
) -> str:
    """List team members"""
    members = await client.list_team_members(team_id, page=page, limit=limit)
    result = {"success": True, "count": len(members), "members": members}
    return json.dumps(result, indent=2)
