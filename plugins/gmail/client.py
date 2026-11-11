"""Gmail API Client — OAuth refresh-token + Gmail REST API v1.

Holds the per-site OAuth credentials (client_id, client_secret,
refresh_token). Refreshes the short-lived access token on demand and caches
it until near expiry, then calls the Gmail REST API with a Bearer token.

The plugin receives these from SiteManager at call time (decrypted from the
SQLite store). It never reads env vars for per-site creds and never persists
a credential file — that avoids the volume-overrides-env silent-failure
class documented for other apps on this host.
"""

import logging
import time
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# Gmail API base — there is no per-site URL; it is always this host.
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Refresh a little before the real expiry to avoid edge races.
_TOKEN_REFRESH_MARGIN_S = 60


class GmailClient:
    """Gmail REST API client with automatic OAuth token refresh."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        user_email: str | None = None,
    ):
        """Initialize the Gmail client.

        Args:
            client_id: GCP OAuth Desktop client ID.
            client_secret: GCP OAuth Desktop client secret.
            refresh_token: Long-lived Google refresh token (gmail.modify scope).
            user_email: Optional account email. Gmail API allows ``me`` as the
                user id; this is kept only for display/health diagnostics.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.user_email = user_email
        self.logger = logging.getLogger(f"GmailClient.{user_email or 'me'}")

        self._access_token: str | None = None
        self._expires_at: float = 0.0

    # --- OAuth token management ---

    async def _ensure_access_token(self) -> str:
        """Return a valid access token, refreshing it if expired/missing."""
        if self._access_token and time.time() < (self._expires_at - _TOKEN_REFRESH_MARGIN_S):
            return self._access_token

        self.logger.debug("Refreshing Gmail access token")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Gmail token refresh failed (HTTP {resp.status}): {text}")
                data = await resp.json()

        self._access_token = data["access_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._access_token

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        user_id: str = "me",
    ) -> Any:
        """Make an authenticated Gmail API request.

        Args:
            method: HTTP method.
            path: API path under /gmail/v1 (without the leading slash).
            params: Query parameters (None values dropped).
            json_data: JSON body (None values dropped).
            user_id: Gmail user id; ``me`` means the authorized account.

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            Exception: On non-2xx responses with status + body.
        """
        token = await self._ensure_access_token()
        # All Gmail v1 endpoints are /gmail/v1/users/{userId}/<resource>.
        url = f"{GMAIL_API_BASE}/users/{user_id}/{path.lstrip('/')}"

        if params:
            params = {k: v for k, v in params.items() if v is not None}
        if json_data:
            json_data = {k: v for k, v in json_data.items() if v is not None}

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        self.logger.debug(f"{method} {url}")

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=url,
                params=params,
                json=json_data if json_data is not None else None,
                headers=headers,
            ) as response:
                if response.status == 204:
                    return {"success": True}
                try:
                    body = await response.json()
                except Exception:
                    text = await response.text()
                    if response.status >= 400:
                        raise Exception(f"Gmail API error (status {response.status}): {text}")
                    return {"success": True, "message": text}

                if response.status >= 400:
                    msg = body.get("error", {}).get("message") if isinstance(body, dict) else None
                    raise Exception(f"Gmail API error (status {response.status}): {msg or body}")
                return body

    # --- Profile / health ---

    async def get_profile(self, user_id: str = "me") -> dict:
        """Get the user's Gmail profile (used by health check + Test Connection)."""
        return await self._request("GET", "profile", user_id=user_id)

    # --- Messages ---

    async def list_messages(
        self,
        q: str | None = None,
        max_results: int = 10,
        label_ids: list[str] | None = None,
        page_token: str | None = None,
        user_id: str = "me",
    ) -> dict:
        """List messages matching a query / labels."""
        params: dict[str, Any] = {"maxResults": max_results}
        if q:
            params["q"] = q
        if label_ids:
            params["labelIds"] = ",".join(label_ids)
        if page_token:
            params["pageToken"] = page_token
        return await self._request("GET", "messages", params=params, user_id=user_id)

    async def get_message(
        self,
        message_id: str,
        format: str = "full",
        user_id: str = "me",
    ) -> dict:
        """Get a single message by id.

        format: ``minimal`` | ``metadata`` | ``full`` | ``raw``.
        """
        params = {"format": format}
        return await self._request("GET", f"messages/{message_id}", params=params, user_id=user_id)

    async def trash_message(self, message_id: str, user_id: str = "me") -> dict:
        """Move a message to trash."""
        return await self._request("POST", f"messages/{message_id}/trash", user_id=user_id)

    async def untrash_message(self, message_id: str, user_id: str = "me") -> dict:
        """Remove a message from trash."""
        return await self._request("POST", f"messages/{message_id}/untrash", user_id=user_id)

    # --- Labels (covers mark read/unread + add/remove label) ---

    async def list_labels(self, user_id: str = "me") -> dict:
        """List all user + system labels."""
        return await self._request("GET", "labels", user_id=user_id)

    async def get_label(self, label_id: str, user_id: str = "me") -> dict:
        """Get a single label by id."""
        return await self._request("GET", f"labels/{label_id}", user_id=user_id)

    async def modify_message_labels(
        self,
        message_id: str,
        add_label_ids: list[str] | None = None,
        remove_label_ids: list[str] | None = None,
        user_id: str = "me",
    ) -> dict:
        """Add and/or remove labels on a message.

        Mark read  → removeLabelIds=["UNREAD"]
        Mark unread → addLabelIds=["UNREAD"]
        Star       → addLabelIds=["STARRED"]
        """
        json_data: dict[str, Any] = {}
        if add_label_ids:
            json_data["addLabelIds"] = add_label_ids
        if remove_label_ids:
            json_data["removeLabelIds"] = remove_label_ids
        return await self._request(
            "POST", f"messages/{message_id}/modify", json_data=json_data, user_id=user_id
        )

    # --- Attachments ---

    async def get_attachment(
        self,
        message_id: str,
        attachment_id: str,
        user_id: str = "me",
    ) -> dict:
        """Get an attachment's metadata + base64-encoded payload by id."""
        return await self._request(
            "GET",
            f"messages/{message_id}/attachments/{attachment_id}",
            user_id=user_id,
        )
