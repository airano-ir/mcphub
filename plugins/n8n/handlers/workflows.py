"""Workflow Handler - manages n8n workflows"""

import json
from typing import Any

from plugins.n8n.client import N8nClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === LIST WORKFLOWS ===
        {
            "name": "list_workflows",
            "method_name": "list_workflows",
            "description": "List all n8n workflows with optional filters. Returns workflow ID, name, active status, tags, and metadata. All filter parameters are OPTIONAL.",
            "schema": {
                "type": "object",
                "properties": {
                    "active": {
                        "type": "boolean",
                        "description": "OPTIONAL: Filter by active/inactive status. Omit for all workflows.",
                    },
                    "tags": {
                        "type": "string",
                        "description": "OPTIONAL: Filter by tag name(s), comma-separated. Omit for all workflows.",
                    },
                    "name": {
                        "type": "string",
                        "description": "OPTIONAL: Filter by workflow name (partial match). Omit for all workflows.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum workflows to return",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 250,
                    },
                    "cursor": {
                        "type": "string",
                        "description": "OPTIONAL: Pagination cursor for next page.",
                    },
                },
            },
            "scope": "read",
        },
        # === GET WORKFLOW ===
        {
            "name": "get_workflow",
            "method_name": "get_workflow",
            "description": "Get detailed information about a specific workflow including nodes, connections, and settings.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow ID", "minLength": 1}
                },
                "required": ["workflow_id"],
            },
            "scope": "read",
        },
        # === CREATE WORKFLOW ===
        {
            "name": "create_workflow",
            "method_name": "create_workflow",
            "description": "Create a new workflow from JSON definition. Workflow will be inactive by default. Note: settings and static_data are OPTIONAL - omit them entirely if not needed.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Workflow name", "minLength": 1},
                    "nodes": {
                        "type": "array",
                        "description": "Array of node definitions",
                        "items": {"type": "object"},
                        "default": [],
                    },
                    "connections": {
                        "type": "object",
                        "description": "Node connections definition",
                        "default": {},
                    },
                    "settings": {
                        "type": "object",
                        "description": "OPTIONAL: Workflow settings (timezone, error workflow, etc.). Omit this parameter if not needed.",
                        "default": {},
                    },
                    "static_data": {
                        "type": "object",
                        "description": "OPTIONAL: Static data for the workflow. Omit this parameter if not needed.",
                        "default": {},
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        # === UPDATE WORKFLOW ===
        {
            "name": "update_workflow",
            "method_name": "update_workflow",
            "description": "Update an existing workflow. Can modify nodes, connections, settings, or name. All parameters except workflow_id are OPTIONAL - omit them to keep current values.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID to update",
                        "minLength": 1,
                    },
                    "name": {
                        "type": "string",
                        "description": "OPTIONAL: New workflow name. Omit to keep current.",
                    },
                    "nodes": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "OPTIONAL: Updated node definitions. Omit to keep current.",
                    },
                    "connections": {
                        "type": "object",
                        "description": "OPTIONAL: Updated connections. Omit to keep current.",
                    },
                    "settings": {
                        "type": "object",
                        "description": "OPTIONAL: Updated settings. Omit to keep current.",
                    },
                },
                "required": ["workflow_id"],
            },
            "scope": "write",
        },
        # === DELETE WORKFLOW ===
        {
            "name": "delete_workflow",
            "method_name": "delete_workflow",
            "description": "Permanently delete a workflow. This action cannot be undone.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID to delete",
                        "minLength": 1,
                    }
                },
                "required": ["workflow_id"],
            },
            "scope": "admin",
        },
        # === ACTIVATE WORKFLOW ===
        {
            "name": "activate_workflow",
            "method_name": "activate_workflow",
            "description": "Activate a workflow so it runs automatically when triggered. Workflow must have at least one trigger node.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID to activate",
                        "minLength": 1,
                    }
                },
                "required": ["workflow_id"],
            },
            "scope": "write",
        },
        # === DEACTIVATE WORKFLOW ===
        {
            "name": "deactivate_workflow",
            "method_name": "deactivate_workflow",
            "description": "Deactivate a workflow. It will no longer run automatically but can still be executed manually.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID to deactivate",
                        "minLength": 1,
                    }
                },
                "required": ["workflow_id"],
            },
            "scope": "write",
        },
        # === EXECUTE WORKFLOW ===
        {
            "name": "execute_workflow",
            "method_name": "execute_workflow",
            "description": "Manually execute a workflow and return execution ID. Use get_execution to check status and results.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID to execute",
                        "minLength": 1,
                    }
                },
                "required": ["workflow_id"],
            },
            "scope": "write",
        },
        # === EXECUTE WORKFLOW WITH DATA ===
        {
            "name": "execute_workflow_with_data",
            "method_name": "execute_workflow_with_data",
            "description": "Execute workflow with custom input data. Useful for workflows with webhook or manual triggers.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID to execute",
                        "minLength": 1,
                    },
                    "data": {
                        "type": "object",
                        "description": "Input data to pass to workflow trigger node",
                    },
                },
                "required": ["workflow_id", "data"],
            },
            "scope": "write",
        },
        # === DUPLICATE WORKFLOW ===
        {
            "name": "duplicate_workflow",
            "method_name": "duplicate_workflow",
            "description": "Create a copy of an existing workflow with a new name.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID to duplicate",
                        "minLength": 1,
                    },
                    "new_name": {
                        "type": "string",
                        "description": "Name for the duplicated workflow",
                        "minLength": 1,
                    },
                },
                "required": ["workflow_id", "new_name"],
            },
            "scope": "write",
        },
        # === EXPORT WORKFLOW ===
        {
            "name": "export_workflow",
            "method_name": "export_workflow",
            "description": "Export a workflow as JSON. Can be used for backup or sharing.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "Workflow ID to export",
                        "minLength": 1,
                    }
                },
                "required": ["workflow_id"],
            },
            "scope": "read",
        },
        # === IMPORT WORKFLOW ===
        {
            "name": "import_workflow",
            "method_name": "import_workflow",
            "description": "Import a workflow from JSON definition. Similar to create but accepts full workflow JSON.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_json": {
                        "type": "object",
                        "description": "Full workflow JSON to import",
                    },
                    "name_override": {
                        "type": "string",
                        "description": "OPTIONAL: Override the workflow name from JSON. Omit to use the name from JSON.",
                    },
                },
                "required": ["workflow_json"],
            },
            "scope": "write",
        },
        # === GET WORKFLOW TAGS ===
        {
            "name": "get_workflow_tags",
            "method_name": "get_workflow_tags",
            "description": "Get list of tags assigned to a workflow.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow ID", "minLength": 1}
                },
                "required": ["workflow_id"],
            },
            "scope": "read",
        },
        # === SET WORKFLOW TAGS ===
        {
            "name": "set_workflow_tags",
            "method_name": "set_workflow_tags",
            "description": "Assign tags to a workflow. Replaces existing tags. Pass empty array [] to remove all tags.",
            "schema": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow ID", "minLength": 1},
                    "tag_ids": {
                        "type": "array",
                        "description": "List of tag IDs to assign. Use empty array [] to remove all tags. Get tag IDs using n8n_list_tags first.",
                        "items": {"type": "string"},
                        "default": [],
                    },
                },
                "required": ["workflow_id"],
            },
            "scope": "write",
        },
    ]

# === HANDLER FUNCTIONS ===

async def list_workflows(
    client: N8nClient,
    active: bool | None = None,
    tags: str | None = None,
    name: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> str:
    """List all workflows with filters"""
    try:
        response = await client.list_workflows(
            active=active, tags=tags, name=name, limit=limit, cursor=cursor
        )

        workflows = response.get("data", [])
        next_cursor = response.get("nextCursor")

        result = {
            "success": True,
            "count": len(workflows),
            "workflows": [
                {
                    "id": w.get("id"),
                    "name": w.get("name"),
                    "active": w.get("active"),
                    "tags": [t.get("name") for t in w.get("tags", [])],
                    "created_at": w.get("createdAt"),
                    "updated_at": w.get("updatedAt"),
                }
                for w in workflows
            ],
            "next_cursor": next_cursor,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_workflow(client: N8nClient, workflow_id: str) -> str:
    """Get workflow details"""
    try:
        workflow = await client.get_workflow(workflow_id)

        result = {
            "success": True,
            "workflow": {
                "id": workflow.get("id"),
                "name": workflow.get("name"),
                "active": workflow.get("active"),
                "nodes": workflow.get("nodes", []),
                "connections": workflow.get("connections", {}),
                "settings": workflow.get("settings", {}),
                "static_data": workflow.get("staticData"),
                "tags": [t.get("name") for t in workflow.get("tags", [])],
                "created_at": workflow.get("createdAt"),
                "updated_at": workflow.get("updatedAt"),
            },
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def create_workflow(
    client: N8nClient,
    name: str,
    nodes: list[dict[str, Any]] | None = None,
    connections: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    static_data: dict[str, Any] | None = None,
) -> str:
    """Create a new workflow"""
    try:
        # Use defaults for optional parameters
        data = {
            "name": name,
            "nodes": nodes if nodes is not None else [],
            "connections": connections if connections is not None else {},
        }

        # Only add settings/static_data if provided and non-empty
        if settings and isinstance(settings, dict) and len(settings) > 0:
            data["settings"] = settings
        if static_data and isinstance(static_data, dict) and len(static_data) > 0:
            data["staticData"] = static_data

        workflow = await client.create_workflow(data)

        result = {
            "success": True,
            "message": f"Workflow '{name}' created successfully",
            "workflow": {
                "id": workflow.get("id"),
                "name": workflow.get("name"),
                "active": workflow.get("active", False),
            },
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def update_workflow(
    client: N8nClient,
    workflow_id: str,
    name: str | None = None,
    nodes: list[dict[str, Any]] | None = None,
    connections: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
) -> str:
    """Update an existing workflow"""
    try:
        # Get current workflow first
        current = await client.get_workflow(workflow_id)

        # Build update data
        data = {
            "name": name or current.get("name"),
            "nodes": nodes or current.get("nodes", []),
            "connections": connections or current.get("connections", {}),
        }

        if settings:
            data["settings"] = settings

        workflow = await client.update_workflow(workflow_id, data)

        result = {
            "success": True,
            "message": f"Workflow '{workflow.get('name')}' updated successfully",
            "workflow": {
                "id": workflow.get("id"),
                "name": workflow.get("name"),
                "active": workflow.get("active"),
            },
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def delete_workflow(client: N8nClient, workflow_id: str) -> str:
    """Delete a workflow"""
    try:
        await client.delete_workflow(workflow_id)

        result = {"success": True, "message": f"Workflow {workflow_id} deleted successfully"}

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def activate_workflow(client: N8nClient, workflow_id: str) -> str:
    """Activate a workflow"""
    try:
        workflow = await client.activate_workflow(workflow_id)

        result = {
            "success": True,
            "message": f"Workflow '{workflow.get('name')}' activated successfully",
            "workflow": {
                "id": workflow.get("id"),
                "name": workflow.get("name"),
                "active": workflow.get("active"),
            },
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def deactivate_workflow(client: N8nClient, workflow_id: str) -> str:
    """Deactivate a workflow"""
    try:
        workflow = await client.deactivate_workflow(workflow_id)

        result = {
            "success": True,
            "message": f"Workflow '{workflow.get('name')}' deactivated successfully",
            "workflow": {
                "id": workflow.get("id"),
                "name": workflow.get("name"),
                "active": workflow.get("active"),
            },
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def execute_workflow(client: N8nClient, workflow_id: str) -> str:
    """Execute a workflow manually"""
    try:
        execution = await client.execute_workflow(workflow_id)

        result = {
            "success": True,
            "message": "Workflow execution started",
            "execution": {
                "id": execution.get("id"),
                "workflow_id": workflow_id,
                "status": execution.get("status", "running"),
            },
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def execute_workflow_with_data(
    client: N8nClient, workflow_id: str, data: dict[str, Any]
) -> str:
    """Execute workflow with custom input data"""
    try:
        execution = await client.execute_workflow(workflow_id, data=data)

        result = {
            "success": True,
            "message": "Workflow execution started with custom data",
            "execution": {
                "id": execution.get("id"),
                "workflow_id": workflow_id,
                "status": execution.get("status", "running"),
                "input_data": data,
            },
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def duplicate_workflow(client: N8nClient, workflow_id: str, new_name: str) -> str:
    """Duplicate a workflow"""
    try:
        # Get the original workflow
        original = await client.get_workflow(workflow_id)

        # Create new workflow with same structure
        data = {
            "name": new_name,
            "nodes": original.get("nodes", []),
            "connections": original.get("connections", {}),
            "settings": original.get("settings", {}),
        }

        new_workflow = await client.create_workflow(data)

        result = {
            "success": True,
            "message": f"Workflow duplicated as '{new_name}'",
            "original": {"id": original.get("id"), "name": original.get("name")},
            "duplicate": {"id": new_workflow.get("id"), "name": new_workflow.get("name")},
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def export_workflow(client: N8nClient, workflow_id: str) -> str:
    """Export workflow as JSON"""
    try:
        workflow = await client.get_workflow(workflow_id)

        # Return full workflow JSON for export
        result = {"success": True, "workflow_json": workflow}

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def import_workflow(
    client: N8nClient, workflow_json: dict[str, Any], name_override: str | None = None
) -> str:
    """Import workflow from JSON"""
    try:
        # Use name override if provided
        if name_override:
            workflow_json["name"] = name_override

        # Ensure required fields
        if "nodes" not in workflow_json:
            workflow_json["nodes"] = []
        if "connections" not in workflow_json:
            workflow_json["connections"] = {}

        workflow = await client.create_workflow(workflow_json)

        result = {
            "success": True,
            "message": f"Workflow '{workflow.get('name')}' imported successfully",
            "workflow": {
                "id": workflow.get("id"),
                "name": workflow.get("name"),
                "active": workflow.get("active", False),
            },
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def get_workflow_tags(client: N8nClient, workflow_id: str) -> str:
    """Get tags assigned to a workflow"""
    try:
        tags = await client.get_workflow_tags(workflow_id)

        result = {"success": True, "workflow_id": workflow_id, "tags": tags}

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)

async def set_workflow_tags(
    client: N8nClient, workflow_id: str, tag_ids: list[str] | None = None
) -> str:
    """Set tags for a workflow"""
    try:
        # Use empty list if tag_ids is None
        tags_to_set = tag_ids if tag_ids is not None else []

        # Get current workflow
        current = await client.get_workflow(workflow_id)

        # Update with new tags
        data = {
            "name": current.get("name"),
            "nodes": current.get("nodes", []),
            "connections": current.get("connections", {}),
            "tags": [{"id": tid} for tid in tags_to_set],
        }

        workflow = await client.update_workflow(workflow_id, data)

        result = {
            "success": True,
            "message": f"Tags updated for workflow {workflow_id}",
            "workflow_id": workflow_id,
            "tags": [t.get("name") for t in workflow.get("tags", [])],
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
