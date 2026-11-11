"""Message handlers — list, get, search, trash/untrash Gmail messages."""

import json
from typing import Any

from plugins.gmail.client import GmailClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_messages",
            "category": "read",
            "method_name": "list_messages",
            "description": (
                "List Gmail messages. Optionally filter with a Gmail search query "
                "(q), label ids, and paginate. Returns message ids + thread ids; "
                "use gmail_get_message to read a message's content."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "q": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": (
                            "Gmail search query, same syntax as the Gmail search box "
                            "(e.g. 'from:alice@example.com subject:invoice newer_than:7d')."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of messages to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 500,
                    },
                    "label_ids": {
                        "anyOf": [
                            {"type": "array", "items": {"type": "string"}, "minItems": 1},
                            {"type": "null"},
                        ],
                        "description": (
                            "Only return messages with these label ids (e.g. INBOX, UNREAD, "
                            "STARRED, or a user label id)."
                        ),
                    },
                    "page_token": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Page token from a previous list_messages response for pagination.",
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_message",
            "category": "read",
            "method_name": "get_message",
            "description": (
                "Get a single Gmail message by id, including headers and (with "
                "format=full) the body parts. Use format=metadata for headers only "
                "(cheaper) or format=raw for the full RFC822 message."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message id (from list_messages)",
                        "minLength": 1,
                    },
                    "format": {
                        "type": "string",
                        "description": "Level of detail to return",
                        "enum": ["minimal", "metadata", "full", "raw"],
                        "default": "full",
                    },
                },
                "required": ["message_id"],
            },
            "scope": "read",
        },
        {
            "name": "trash_message",
            "category": "write",
            "method_name": "trash_message",
            "description": "Move a Gmail message to trash. Recoverable until ~30 days.",
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message id to trash",
                        "minLength": 1,
                    },
                },
                "required": ["message_id"],
            },
            "scope": "write",
        },
        {
            "name": "untrash_message",
            "category": "write",
            "method_name": "untrash_message",
            "description": "Remove a message from trash (restore to inbox).",
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message id to restore",
                        "minLength": 1,
                    },
                },
                "required": ["message_id"],
            },
            "scope": "write",
        },
        {
            "name": "get_attachment",
            "category": "read",
            "method_name": "get_attachment",
            "description": (
                "Get a message attachment by id. Returns the attachment filename, "
                "mime type, size, and base64-encoded data. Find attachment ids in a "
                "get_message (format=full) response under parts[].body.attachmentId."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message id containing the attachment",
                        "minLength": 1,
                    },
                    "attachment_id": {
                        "type": "string",
                        "description": "Attachment id from the message body part",
                        "minLength": 1,
                    },
                },
                "required": ["message_id", "attachment_id"],
            },
            "scope": "read",
        },
    ]


# --- Handler functions ---


async def list_messages(
    client: GmailClient,
    q: str | None = None,
    max_results: int = 10,
    label_ids: list[str] | None = None,
    page_token: str | None = None,
) -> str:
    """List messages matching a query / labels."""
    data = await client.list_messages(
        q=q, max_results=max_results, label_ids=label_ids, page_token=page_token
    )
    result = {
        "success": True,
        "count": len(data.get("messages", [])),
        "messages": data.get("messages", []),
        "next_page_token": data.get("nextPageToken"),
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_message(client: GmailClient, message_id: str, format: str = "full") -> str:
    """Get a single message."""
    data = await client.get_message(message_id, format=format)
    result = {"success": True, "message": data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def trash_message(client: GmailClient, message_id: str) -> str:
    """Move a message to trash."""
    await client.trash_message(message_id)
    result = {"success": True, "message": f"Message '{message_id}' moved to trash"}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def untrash_message(client: GmailClient, message_id: str) -> str:
    """Remove a message from trash."""
    await client.untrash_message(message_id)
    result = {"success": True, "message": f"Message '{message_id}' restored from trash"}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_attachment(client: GmailClient, message_id: str, attachment_id: str) -> str:
    """Get an attachment by id."""
    data = await client.get_attachment(message_id, attachment_id)
    result = {"success": True, "attachment": data}
    return json.dumps(result, indent=2, ensure_ascii=False)
