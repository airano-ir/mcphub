"""Gmail Plugin — Clean Architecture.

Read + manage a Gmail inbox through the Gmail REST API v1 using a long-lived
OAuth refresh token (scope ``gmail.modify``). Provides message
listing/search/reading, attachments, label management (mark read/unread,
add/remove labels), and trash/untrash. Sending (``gmail.send`` scope) is
deferred to a later iteration.

The plugin receives per-site credentials (client_id, client_secret,
refresh_token) decrypted from the SQLite store at call time. It never reads
env vars for per-site creds and never persists a credential file.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.gmail import handlers
from plugins.gmail.client import GmailClient


class GmailPlugin(BasePlugin):
    """Gmail project plugin — Clean architecture.

    Provides Gmail inbox management capabilities including:
    - Message listing / search / reading / trash / untrash
    - Attachments
    - Label listing + mark read/unread + add/remove labels
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier."""
        return "gmail"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys."""
        return ["client_id", "client_secret", "refresh_token"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """Initialize the Gmail plugin.

        Args:
            config: Configuration dictionary containing:
                - client_id: GCP OAuth Desktop client ID
                - client_secret: GCP OAuth Desktop client secret
                - refresh_token: Long-lived Google refresh token (gmail.modify)
                - user_email: (Optional) account email, for display only
            project_id: Optional project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        self.client = GmailClient(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            refresh_token=config["refresh_token"],
            user_email=config.get("user_email"),
        )

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """Return all tool specifications for ToolGenerator."""
        specs: list[dict[str, Any]] = []
        specs.extend(handlers.messages.get_tool_specifications())
        specs.extend(handlers.labels.get_tool_specifications())
        return specs

    def __getattr__(self, name: str):
        """Dynamically delegate method calls to handler modules.

        Args:
            name: Method name being called.

        Returns:
            Handler function from the messages or labels handler module.
        """
        handler_modules = [handlers.messages, handlers.labels]

        for module in handler_modules:
            if hasattr(module, name):
                func = getattr(module, name)

                async def wrapper(_func=func, **kwargs):
                    return await _func(self.client, **kwargs)

                return wrapper

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    async def health_check(self) -> dict[str, Any]:
        """Check if the Gmail account is accessible via the refresh token."""
        try:
            profile = await self.client.get_profile()
            email = profile.get("emailAddress", "?")
            return {
                "healthy": True,
                "message": f"Gmail account '{email}' is accessible",
            }
        except Exception as e:
            return {"healthy": False, "message": f"Gmail health check failed: {str(e)}"}

    async def probe_credential_capabilities(self) -> dict[str, Any]:
        """F.7e — report what the Gmail credential can do.

        The refresh token's scope (``gmail.modify``) is fixed at consent time
        and not discoverable from the API itself, so report the known granted
        capability set deterministically after confirming the token refreshes
        successfully via ``getProfile``.
        """
        try:
            profile = await self.client.get_profile()
        except Exception as exc:  # noqa: BLE001
            return {
                "probe_available": False,
                "granted": [],
                "source": "gmail_oauth_scope",
                "reason": f"profile_failed: {exc}",
            }

        return {
            "probe_available": True,
            "granted": [
                "gmail.read",  # list/get messages, labels, attachments
                "gmail.modify",  # mark read/unread, add/remove labels, trash/untrash
            ],
            "source": "gmail_oauth_scope",
            "reason": f"profile_ok: {profile.get('emailAddress', '?')}",
        }
