"""
Messaging Handler - manages Appwrite messaging (Email, SMS, Push notifications)

Phase I.4: 12 tools
- Topics: 4 (list, get, create, delete)
- Subscribers: 2 (create, delete)
- Messages: 6 (list, get, send_email, send_sms, send_push, delete)
"""

import json
from typing import Any

from plugins.appwrite.client import AppwriteClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (12 tools)"""
    return [
        # =====================
        # TOPICS (4)
        # =====================
        {
            "name": "list_topics",
            "method_name": "list_topics",
            "description": "List all messaging topics. Topics are groups for sending messages to multiple subscribers.",
            "schema": {
                "type": "object",
                "properties": {
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_topic",
            "method_name": "get_topic",
            "description": "Get topic details by ID.",
            "schema": {
                "type": "object",
                "properties": {"topic_id": {"type": "string", "description": "Topic ID"}},
                "required": ["topic_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_topic",
            "method_name": "create_topic",
            "description": "Create a new messaging topic.",
            "schema": {
                "type": "object",
                "properties": {
                    "topic_id": {
                        "type": "string",
                        "description": "Unique topic ID. Use 'unique()' for auto-generation",
                    },
                    "name": {"type": "string", "description": "Topic name"},
                    "subscribe": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Permissions for who can subscribe (e.g., ['users', 'any'])",
                    },
                },
                "required": ["topic_id", "name"],
            },
            "scope": "write",
        },
        {
            "name": "delete_topic",
            "method_name": "delete_topic",
            "description": "Delete a messaging topic.",
            "schema": {
                "type": "object",
                "properties": {"topic_id": {"type": "string", "description": "Topic ID to delete"}},
                "required": ["topic_id"],
            },
            "scope": "write",
        },
        # =====================
        # SUBSCRIBERS (2)
        # =====================
        {
            "name": "create_subscriber",
            "method_name": "create_subscriber",
            "description": "Add a subscriber to a topic.",
            "schema": {
                "type": "object",
                "properties": {
                    "topic_id": {"type": "string", "description": "Topic ID"},
                    "subscriber_id": {
                        "type": "string",
                        "description": "Unique subscriber ID. Use 'unique()' for auto-generation",
                    },
                    "target_id": {
                        "type": "string",
                        "description": "Target ID (user's target for messaging)",
                    },
                },
                "required": ["topic_id", "subscriber_id", "target_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_subscriber",
            "method_name": "delete_subscriber",
            "description": "Remove a subscriber from a topic.",
            "schema": {
                "type": "object",
                "properties": {
                    "topic_id": {"type": "string", "description": "Topic ID"},
                    "subscriber_id": {"type": "string", "description": "Subscriber ID to remove"},
                },
                "required": ["topic_id", "subscriber_id"],
            },
            "scope": "write",
        },
        # =====================
        # MESSAGES (6)
        # =====================
        {
            "name": "list_messages",
            "method_name": "list_messages",
            "description": "List all messages (sent and draft).",
            "schema": {
                "type": "object",
                "properties": {
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query strings for filtering",
                    },
                    "search": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Search term",
                    },
                },
                "required": [],
            },
            "scope": "read",
        },
        {
            "name": "get_message",
            "method_name": "get_message",
            "description": "Get message details by ID.",
            "schema": {
                "type": "object",
                "properties": {"message_id": {"type": "string", "description": "Message ID"}},
                "required": ["message_id"],
            },
            "scope": "read",
        },
        {
            "name": "send_email",
            "method_name": "send_email",
            "description": "Send an email message. Requires configured email provider.",
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Unique message ID. Use 'unique()' for auto-generation",
                    },
                    "subject": {"type": "string", "description": "Email subject"},
                    "content": {
                        "type": "string",
                        "description": "Email content (HTML supported if html=true)",
                    },
                    "topics": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Topic IDs to send to",
                    },
                    "users": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "User IDs to send to",
                    },
                    "targets": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Target IDs to send to",
                    },
                    "cc": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "CC recipients",
                    },
                    "bcc": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "BCC recipients",
                    },
                    "html": {
                        "type": "boolean",
                        "description": "Send as HTML email",
                        "default": True,
                    },
                    "draft": {
                        "type": "boolean",
                        "description": "Save as draft instead of sending",
                        "default": False,
                    },
                    "scheduled_at": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Schedule send time (ISO 8601 format)",
                    },
                },
                "required": ["message_id", "subject", "content"],
            },
            "scope": "write",
        },
        {
            "name": "send_sms",
            "method_name": "send_sms",
            "description": "Send an SMS message. Requires configured SMS provider.",
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Unique message ID. Use 'unique()' for auto-generation",
                    },
                    "content": {"type": "string", "description": "SMS content"},
                    "topics": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Topic IDs to send to",
                    },
                    "users": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "User IDs to send to",
                    },
                    "targets": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Target IDs to send to",
                    },
                    "draft": {"type": "boolean", "description": "Save as draft", "default": False},
                    "scheduled_at": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Schedule send time (ISO 8601 format)",
                    },
                },
                "required": ["message_id", "content"],
            },
            "scope": "write",
        },
        {
            "name": "send_push",
            "method_name": "send_push",
            "description": "Send a push notification. Requires configured push provider (FCM/APNs).",
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Unique message ID. Use 'unique()' for auto-generation",
                    },
                    "title": {"type": "string", "description": "Notification title"},
                    "body": {"type": "string", "description": "Notification body"},
                    "topics": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Topic IDs to send to",
                    },
                    "users": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "User IDs to send to",
                    },
                    "targets": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Target IDs to send to",
                    },
                    "data": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Custom data payload",
                    },
                    "action": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Action URL",
                    },
                    "image": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Image URL",
                    },
                    "icon": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Icon URL",
                    },
                    "sound": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Sound name",
                    },
                    "badge": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Badge number (iOS)",
                    },
                    "draft": {"type": "boolean", "description": "Save as draft", "default": False},
                    "scheduled_at": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Schedule send time (ISO 8601 format)",
                    },
                },
                "required": ["message_id", "title", "body"],
            },
            "scope": "write",
        },
        {
            "name": "delete_message",
            "method_name": "delete_message",
            "description": "Delete a message.",
            "schema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Message ID to delete"}
                },
                "required": ["message_id"],
            },
            "scope": "write",
        },
    ]


# =====================
# HANDLER FUNCTIONS
# =====================


async def list_topics(
    client: AppwriteClient, queries: list[str] | None = None, search: str | None = None
) -> str:
    """List all topics."""
    try:
        result = await client.list_topics(queries=queries, search=search)
        topics = result.get("topics", [])

        response = {"success": True, "total": result.get("total", len(topics)), "topics": topics}
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_topic(client: AppwriteClient, topic_id: str) -> str:
    """Get topic by ID."""
    try:
        result = await client.get_topic(topic_id)
        return json.dumps({"success": True, "topic": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_topic(
    client: AppwriteClient, topic_id: str, name: str, subscribe: list[str] | None = None
) -> str:
    """Create a new topic."""
    try:
        result = await client.create_topic(topic_id=topic_id, name=name, subscribe=subscribe)
        return json.dumps(
            {"success": True, "message": f"Topic '{name}' created successfully", "topic": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_topic(client: AppwriteClient, topic_id: str) -> str:
    """Delete topic."""
    try:
        await client.delete_topic(topic_id)
        return json.dumps(
            {"success": True, "message": f"Topic '{topic_id}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_subscriber(
    client: AppwriteClient, topic_id: str, subscriber_id: str, target_id: str
) -> str:
    """Add subscriber to topic."""
    try:
        result = await client.create_subscriber(
            topic_id=topic_id, subscriber_id=subscriber_id, target_id=target_id
        )
        return json.dumps(
            {"success": True, "message": "Subscriber added to topic", "subscriber": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_subscriber(client: AppwriteClient, topic_id: str, subscriber_id: str) -> str:
    """Remove subscriber from topic."""
    try:
        await client.delete_subscriber(topic_id, subscriber_id)
        return json.dumps(
            {"success": True, "message": f"Subscriber '{subscriber_id}' removed from topic"},
            indent=2,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def list_messages(
    client: AppwriteClient, queries: list[str] | None = None, search: str | None = None
) -> str:
    """List all messages."""
    try:
        result = await client.list_messages(queries=queries, search=search)
        messages = result.get("messages", [])

        response = {
            "success": True,
            "total": result.get("total", len(messages)),
            "messages": messages,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_message(client: AppwriteClient, message_id: str) -> str:
    """Get message by ID."""
    try:
        result = await client.get_message(message_id)
        return json.dumps({"success": True, "message": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def send_email(
    client: AppwriteClient,
    message_id: str,
    subject: str,
    content: str,
    topics: list[str] | None = None,
    users: list[str] | None = None,
    targets: list[str] | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    html: bool = True,
    draft: bool = False,
    scheduled_at: str | None = None,
) -> str:
    """Send email message."""
    try:
        result = await client.create_email(
            message_id=message_id,
            subject=subject,
            content=content,
            topics=topics,
            users=users,
            targets=targets,
            cc=cc,
            bcc=bcc,
            html=html,
            draft=draft,
            scheduled_at=scheduled_at,
        )

        action = "saved as draft" if draft else "sent"
        if scheduled_at:
            action = f"scheduled for {scheduled_at}"

        return json.dumps(
            {"success": True, "message": f"Email {action} successfully", "email": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        error_msg = str(e)
        if "provider" in error_msg.lower():
            error_msg += " (Hint: Make sure you have configured an email provider in Appwrite)"
        return json.dumps({"success": False, "error": error_msg}, indent=2)


async def send_sms(
    client: AppwriteClient,
    message_id: str,
    content: str,
    topics: list[str] | None = None,
    users: list[str] | None = None,
    targets: list[str] | None = None,
    draft: bool = False,
    scheduled_at: str | None = None,
) -> str:
    """Send SMS message."""
    try:
        result = await client.create_sms(
            message_id=message_id,
            content=content,
            topics=topics,
            users=users,
            targets=targets,
            draft=draft,
            scheduled_at=scheduled_at,
        )

        action = "saved as draft" if draft else "sent"
        if scheduled_at:
            action = f"scheduled for {scheduled_at}"

        return json.dumps(
            {"success": True, "message": f"SMS {action} successfully", "sms": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        error_msg = str(e)
        if "provider" in error_msg.lower():
            error_msg += " (Hint: Make sure you have configured an SMS provider in Appwrite)"
        return json.dumps({"success": False, "error": error_msg}, indent=2)


async def send_push(
    client: AppwriteClient,
    message_id: str,
    title: str,
    body: str,
    topics: list[str] | None = None,
    users: list[str] | None = None,
    targets: list[str] | None = None,
    data: dict[str, Any] | None = None,
    action: str | None = None,
    image: str | None = None,
    icon: str | None = None,
    sound: str | None = None,
    badge: int | None = None,
    draft: bool = False,
    scheduled_at: str | None = None,
) -> str:
    """Send push notification."""
    try:
        result = await client.create_push(
            message_id=message_id,
            title=title,
            body=body,
            topics=topics,
            users=users,
            targets=targets,
            data_payload=data,
            action=action,
            image=image,
            icon=icon,
            sound=sound,
            badge=badge,
            draft=draft,
            scheduled_at=scheduled_at,
        )

        action_text = "saved as draft" if draft else "sent"
        if scheduled_at:
            action_text = f"scheduled for {scheduled_at}"

        return json.dumps(
            {
                "success": True,
                "message": f"Push notification {action_text} successfully",
                "push": result,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        error_msg = str(e)
        if "provider" in error_msg.lower():
            error_msg += (
                " (Hint: Make sure you have configured a push provider (FCM/APNs) in Appwrite)"
            )
        return json.dumps({"success": False, "error": error_msg}, indent=2)


async def delete_message(client: AppwriteClient, message_id: str) -> str:
    """Delete message."""
    try:
        await client.delete_message(message_id)
        return json.dumps(
            {"success": True, "message": f"Message '{message_id}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
