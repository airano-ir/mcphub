"""Label handlers — list labels, mark read/unread, add/remove labels."""

import json
from typing import Any

from plugins.gmail.client import GmailClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_labels",
            "category": "read",
            "method_name": "list_labels",
            "description": (
                "List all Gmail labels (system + user) with their ids. System label "
                "ids include INBOX, UNREAD, STARRED, IMPORTANT, TRASH, SENT, DRAFT. "
                "Use these ids with mark_read / mark_unread / add_label / remove_label."
            ),
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "mark_read",
            "category": "write",
            "method_name": "mark_read",
            "description": "Mark a message as read (removes the UNREAD label).",
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message id",
                        "minLength": 1,
                    },
                },
                "required": ["message_id"],
            },
            "scope": "write",
        },
        {
            "name": "mark_unread",
            "category": "write",
            "method_name": "mark_unread",
            "description": "Mark a message as unread (adds the UNREAD label).",
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message id",
                        "minLength": 1,
                    },
                },
                "required": ["message_id"],
            },
            "scope": "write",
        },
        {
            "name": "add_label",
            "category": "write",
            "method_name": "add_label",
            "description": (
                "Add one or more labels to a message (e.g. STARRED, IMPORTANT, or a "
                "user label id from list_labels)."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message id",
                        "minLength": 1,
                    },
                    "label_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Label ids to add",
                    },
                },
                "required": ["message_id", "label_ids"],
            },
            "scope": "write",
        },
        {
            "name": "remove_label",
            "category": "write",
            "method_name": "remove_label",
            "description": (
                "Remove one or more labels from a message (e.g. STARRED, INBOX to "
                "archive, or a user label id)."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message id",
                        "minLength": 1,
                    },
                    "label_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Label ids to remove",
                    },
                },
                "required": ["message_id", "label_ids"],
            },
            "scope": "write",
        },
    ]


# --- Handler functions ---


async def list_labels(client: GmailClient) -> str:
    """List all labels."""
    data = await client.list_labels()
    labels = data.get("labels", [])
    result = {"success": True, "count": len(labels), "labels": labels}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def mark_read(client: GmailClient, message_id: str) -> str:
    """Mark a message as read."""
    await client.modify_message_labels(message_id, remove_label_ids=["UNREAD"])
    result = {"success": True, "message": f"Message '{message_id}' marked as read"}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def mark_unread(client: GmailClient, message_id: str) -> str:
    """Mark a message as unread."""
    await client.modify_message_labels(message_id, add_label_ids=["UNREAD"])
    result = {"success": True, "message": f"Message '{message_id}' marked as unread"}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def add_label(client: GmailClient, message_id: str, label_ids: list[str]) -> str:
    """Add labels to a message."""
    await client.modify_message_labels(message_id, add_label_ids=label_ids)
    result = {
        "success": True,
        "message": f"Added labels {label_ids} to message '{message_id}'",
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def remove_label(client: GmailClient, message_id: str, label_ids: list[str]) -> str:
    """Remove labels from a message."""
    await client.modify_message_labels(message_id, remove_label_ids=label_ids)
    result = {
        "success": True,
        "message": f"Removed labels {label_ids} from message '{message_id}'",
    }
    return json.dumps(result, indent=2, ensure_ascii=False)
