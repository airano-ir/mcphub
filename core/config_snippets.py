"""MCP client configuration snippet generation (Track E.3).

Generates copy-paste configuration snippets for connecting AI clients
(Claude Desktop, Claude Code, Cursor, VS Code, ChatGPT) to per-user
MCP endpoints.

Usage:
    from core.config_snippets import generate_config, get_supported_clients

    snippet = generate_config(
        base_url="https://mcp.example.com",
        user_id="abc123",
        alias="myblog",
        api_key="mhu_...",
        client_type="claude_desktop",
    )
"""

import json

# Supported MCP client types
SUPPORTED_CLIENTS = [
    {
        "id": "claude_desktop",
        "label": "Claude Desktop",
        "description": "Anthropic's desktop app for Claude",
    },
    {
        "id": "claude_code",
        "label": "Claude Code",
        "description": "Anthropic's CLI for Claude",
    },
    {
        "id": "cursor",
        "label": "Cursor",
        "description": "AI-first code editor",
    },
    {
        "id": "vscode",
        "label": "VS Code",
        "description": "Visual Studio Code with MCP extension",
    },
    {
        "id": "chatgpt",
        "label": "ChatGPT",
        "description": "OpenAI ChatGPT (URL-based)",
    },
]


def get_supported_clients() -> list[dict[str, str]]:
    """Return the list of supported MCP client types."""
    return SUPPORTED_CLIENTS


def generate_config(
    base_url: str,
    user_id: str,
    alias: str,
    api_key: str,
    client_type: str,
) -> str:
    """Generate a configuration snippet for the given MCP client.

    Args:
        base_url: Public URL of the MCP Hub instance (no trailing slash).
        user_id: User UUID.
        alias: Site alias.
        api_key: User API key (``mhu_...``).
        client_type: One of the supported client type IDs.

    Returns:
        JSON configuration string ready for copy-paste.

    Raises:
        ValueError: If client_type is not supported.
    """
    base_url = base_url.rstrip("/")
    endpoint_url = f"{base_url}/u/{user_id}/{alias}/mcp"
    server_name = f"mcphub-{alias}"

    # Claude Desktop uses streamableHttp; Claude Code, VS Code, Cursor use http
    transport_type = "streamableHttp" if client_type == "claude_desktop" else "http"

    if client_type in ("claude_desktop", "claude_code"):
        config = {
            "mcpServers": {
                server_name: {
                    "type": transport_type,
                    "url": endpoint_url,
                    "headers": {
                        "Authorization": f"Bearer {api_key}",
                    },
                }
            }
        }
        return json.dumps(config, indent=2)

    elif client_type in ("cursor", "vscode"):
        config = {
            "mcp": {
                "servers": {
                    server_name: {
                        "type": transport_type,
                        "url": endpoint_url,
                        "headers": {
                            "Authorization": f"Bearer {api_key}",
                        },
                    }
                }
            }
        }
        return json.dumps(config, indent=2)

    elif client_type == "chatgpt":
        return endpoint_url

    else:
        valid = [c["id"] for c in SUPPORTED_CLIENTS]
        raise ValueError(f"Unsupported client type '{client_type}'. Valid: {valid}")
