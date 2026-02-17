"""Webhook Handler - manages Gitea webhooks for repositories"""

import json
from typing import Any

from plugins.gitea.client import GiteaClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === WEBHOOKS ===
        {
            "name": "list_webhooks",
            "method_name": "list_webhooks",
            "description": "List all webhooks configured for a repository.",
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
            "name": "create_webhook",
            "method_name": "create_webhook",
            "description": "Create a new webhook for a repository to receive event notifications.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "url": {
                        "type": "string",
                        "description": "Webhook URL to send events to",
                        "format": "uri",
                    },
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "create",
                                "delete",
                                "fork",
                                "push",
                                "issues",
                                "issue_assign",
                                "issue_label",
                                "issue_milestone",
                                "issue_comment",
                                "pull_request",
                                "pull_request_assign",
                                "pull_request_label",
                                "pull_request_milestone",
                                "pull_request_comment",
                                "pull_request_review_approved",
                                "pull_request_review_rejected",
                                "pull_request_review_comment",
                                "pull_request_sync",
                                "wiki",
                                "repository",
                                "release",
                            ],
                        },
                        "description": "List of events to trigger webhook",
                        "minItems": 1,
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Content type for webhook payload",
                        "enum": ["json", "form"],
                        "default": "json",
                    },
                    "secret": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Secret for webhook signature verification",
                    },
                    "active": {
                        "type": "boolean",
                        "description": "Activate webhook immediately",
                        "default": True,
                    },
                    "type": {
                        "type": "string",
                        "description": "Webhook type",
                        "enum": [
                            "gitea",
                            "gogs",
                            "slack",
                            "discord",
                            "dingtalk",
                            "telegram",
                            "msteams",
                            "feishu",
                            "wechatwork",
                            "packagist",
                        ],
                        "default": "gitea",
                    },
                },
                "required": ["owner", "repo", "url", "events"],
            },
            "scope": "admin",
        },
        {
            "name": "delete_webhook",
            "method_name": "delete_webhook",
            "description": "Delete a webhook from a repository.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "webhook_id": {
                        "type": "integer",
                        "description": "Webhook ID to delete",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "webhook_id"],
            },
            "scope": "admin",
        },
        {
            "name": "test_webhook",
            "method_name": "test_webhook",
            "description": "Send a test payload to a webhook to verify it's working.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "webhook_id": {
                        "type": "integer",
                        "description": "Webhook ID to test",
                        "minimum": 1,
                    },
                },
                "required": ["owner", "repo", "webhook_id"],
            },
            "scope": "admin",
        },
        {
            "name": "get_webhook",
            "method_name": "get_webhook",
            "description": "Get details of a specific webhook.",
            "schema": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner", "minLength": 1},
                    "repo": {"type": "string", "description": "Repository name", "minLength": 1},
                    "webhook_id": {"type": "integer", "description": "Webhook ID", "minimum": 1},
                },
                "required": ["owner", "repo", "webhook_id"],
            },
            "scope": "read",
        },
    ]


async def list_webhooks(client: GiteaClient, owner: str, repo: str) -> str:
    """List repository webhooks"""
    webhooks = await client.list_webhooks(owner, repo)
    result = {"success": True, "count": len(webhooks), "webhooks": webhooks}
    return json.dumps(result, indent=2)


async def create_webhook(
    client: GiteaClient,
    owner: str,
    repo: str,
    url: str,
    events: list[str],
    content_type: str = "json",
    secret: str | None = None,
    active: bool = True,
    type: str = "gitea",
) -> str:
    """Create a webhook"""
    # Build webhook configuration
    config = {"url": url, "content_type": content_type}
    if secret:
        config["secret"] = secret

    data = {"type": type, "config": config, "events": events, "active": active}

    webhook = await client.create_webhook(owner, repo, data)
    result = {
        "success": True,
        "message": f"Webhook created successfully for {owner}/{repo}",
        "webhook": webhook,
    }
    return json.dumps(result, indent=2)


async def delete_webhook(client: GiteaClient, owner: str, repo: str, webhook_id: int) -> str:
    """Delete a webhook"""
    await client.delete_webhook(owner, repo, webhook_id)
    result = {"success": True, "message": f"Webhook {webhook_id} deleted successfully"}
    return json.dumps(result, indent=2)


async def test_webhook(client: GiteaClient, owner: str, repo: str, webhook_id: int) -> str:
    """Test a webhook"""
    test_result = await client.test_webhook(owner, repo, webhook_id)
    result = {
        "success": True,
        "message": f"Test payload sent to webhook {webhook_id}",
        "result": test_result,
    }
    return json.dumps(result, indent=2)


async def get_webhook(client: GiteaClient, owner: str, repo: str, webhook_id: int) -> str:
    """Get webhook details"""
    webhook = await client.get_webhook(owner, repo, webhook_id)
    result = {"success": True, "webhook": webhook}
    return json.dumps(result, indent=2)
