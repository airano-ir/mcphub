"""
Teams Handler - manages Appwrite teams and memberships

Phase I.2: 10 tools
- Teams: 5 (list, get, create, update, delete)
- Memberships: 5 (list_memberships, create_membership, update_membership, delete_membership, get_membership_status)
"""

import json
from typing import Any

from plugins.appwrite.client import AppwriteClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (10 tools)"""
    return [
        # =====================
        # TEAMS (5)
        # =====================
        {
            "name": "list_teams",
            "method_name": "list_teams",
            "description": "List all teams in the project.",
            "schema": {
                "type": "object",
                "properties": {
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter teams by name",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_team",
            "method_name": "get_team",
            "description": "Get team details by ID.",
            "schema": {
                "type": "object",
                "properties": {"team_id": {"type": "string", "description": "Team ID"}},
                "required": ["team_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_team",
            "method_name": "create_team",
            "description": "Create a new team. Use 'unique()' for auto-generated team ID.",
            "schema": {
                "type": "object",
                "properties": {
                    "team_id": {
                        "type": "string",
                        "description": "Unique team ID. Use 'unique()' for auto-generation",
                    },
                    "name": {"type": "string", "description": "Team name"},
                    "roles": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Array of roles available in this team (e.g., ['owner', 'editor', 'viewer'])",
                    },
                },
                "required": ["team_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "update_team",
            "method_name": "update_team",
            "description": "Update team name.",
            "schema": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "string", "description": "Team ID"},
                    "name": {"type": "string", "description": "New team name"},
                },
                "required": ["team_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_team",
            "method_name": "delete_team",
            "description": "Delete a team and all its memberships. This action is irreversible.",
            "schema": {
                "type": "object",
                "properties": {"team_id": {"type": "string", "description": "Team ID to delete"}},
                "required": ["team_id"],
            },
            "scope": "admin",
        },
        # =====================
        # MEMBERSHIPS (5)
        # =====================
        {
            "name": "list_team_memberships",
            "method_name": "list_team_memberships",
            "description": "List all memberships (members) of a team.",
            "schema": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "string", "description": "Team ID"},
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term to filter members",
                    },
                },
                "required": ["team_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_team_membership",
            "method_name": "create_team_membership",
            "description": "Invite a user to join a team. Can invite by email, phone, or existing user ID.",
            "schema": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "string", "description": "Team ID"},
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Roles to assign to the member",
                    },
                    "email": {
                        "anyOf": [{"type": "string", "format": "email"}, {"type": "null"}],
                        "description": "Email address to invite",
                    },
                    "user_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Existing user ID to add",
                    },
                    "phone": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Phone number to invite",
                    },
                    "url": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Redirect URL after accepting invitation",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Name of the invitee",
                    },
                },
                "required": ["team_id", "roles"],
            },
            "scope": "write",
        },
        {
            "name": "update_membership",
            "method_name": "update_membership",
            "description": "Update team membership roles.",
            "schema": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "string", "description": "Team ID"},
                    "membership_id": {"type": "string", "description": "Membership ID"},
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New roles for the member",
                    },
                },
                "required": ["team_id", "membership_id", "roles"],
            },
            "scope": "write",
        },
        {
            "name": "delete_membership",
            "method_name": "delete_membership",
            "description": "Remove a member from a team.",
            "schema": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "string", "description": "Team ID"},
                    "membership_id": {"type": "string", "description": "Membership ID to remove"},
                },
                "required": ["team_id", "membership_id"],
            },
            "scope": "write",
        },
        {
            "name": "get_team_prefs",
            "method_name": "get_team_prefs",
            "description": "Get team preferences/settings.",
            "schema": {
                "type": "object",
                "properties": {"team_id": {"type": "string", "description": "Team ID"}},
                "required": ["team_id"],
            },
            "scope": "read",
        },
    ]

# =====================
# HANDLER FUNCTIONS
# =====================

async def list_teams(
    client: AppwriteClient, queries: list[str] | None = None, search: str | None = None
) -> str:
    """List all teams."""
    try:
        result = await client.list_teams(queries=queries, search=search)
        teams = result.get("teams", [])

        response = {"success": True, "total": result.get("total", len(teams)), "teams": teams}
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_team(client: AppwriteClient, team_id: str) -> str:
    """Get team by ID."""
    try:
        result = await client.get_team(team_id)
        return json.dumps({"success": True, "team": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_team(
    client: AppwriteClient, team_id: str, name: str, roles: list[str] | None = None
) -> str:
    """Create a new team."""
    try:
        result = await client.create_team(team_id=team_id, name=name, roles=roles)
        return json.dumps(
            {"success": True, "message": f"Team '{name}' created successfully", "team": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_team(client: AppwriteClient, team_id: str, name: str) -> str:
    """Update team name."""
    try:
        result = await client.update_team(team_id=team_id, name=name)
        return json.dumps(
            {"success": True, "message": "Team updated successfully", "team": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_team(client: AppwriteClient, team_id: str) -> str:
    """Delete team."""
    try:
        await client.delete_team(team_id)
        return json.dumps(
            {"success": True, "message": f"Team '{team_id}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def list_team_memberships(
    client: AppwriteClient,
    team_id: str,
    queries: list[str] | None = None,
    search: str | None = None,
) -> str:
    """List team memberships."""
    try:
        result = await client.list_team_memberships(team_id=team_id, queries=queries, search=search)
        memberships = result.get("memberships", [])

        response = {
            "success": True,
            "team_id": team_id,
            "total": result.get("total", len(memberships)),
            "memberships": memberships,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_team_membership(
    client: AppwriteClient,
    team_id: str,
    roles: list[str],
    email: str | None = None,
    user_id: str | None = None,
    phone: str | None = None,
    url: str | None = None,
    name: str | None = None,
) -> str:
    """Create team membership (invite)."""
    try:
        result = await client.create_team_membership(
            team_id=team_id,
            roles=roles,
            email=email,
            user_id=user_id,
            phone=phone,
            url=url,
            name=name,
        )
        target = email or user_id or phone or "user"
        return json.dumps(
            {
                "success": True,
                "message": f"Membership created/invitation sent to {target}",
                "membership": result,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_membership(
    client: AppwriteClient, team_id: str, membership_id: str, roles: list[str]
) -> str:
    """Update membership roles."""
    try:
        result = await client.update_membership(
            team_id=team_id, membership_id=membership_id, roles=roles
        )
        return json.dumps(
            {
                "success": True,
                "message": f"Membership roles updated to: {roles}",
                "membership": result,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_membership(client: AppwriteClient, team_id: str, membership_id: str) -> str:
    """Delete membership."""
    try:
        await client.delete_membership(team_id, membership_id)
        return json.dumps(
            {"success": True, "message": f"Membership '{membership_id}' removed from team"},
            indent=2,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_team_prefs(client: AppwriteClient, team_id: str) -> str:
    """Get team preferences (placeholder - requires team prefs endpoint)."""
    try:
        # Note: Team prefs endpoint may vary by Appwrite version
        # This is a simplified version that returns team info
        result = await client.get_team(team_id)
        return json.dumps(
            {"success": True, "team_id": team_id, "prefs": result.get("prefs", {}), "team": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
