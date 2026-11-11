"""Google Search Console API Client — OAuth refresh-token + Search Console REST API v1.

Holds the per-site OAuth credentials (refresh_token, optionally access_token
and token_expires_at). Refreshes the short-lived access token on demand using
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET from the environment, then calls the
Search Console REST API with a Bearer token.

All requests are read-only (GET). The client does not expose any write methods.
"""

import logging
import os
import time
from typing import Any
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)

# Search Console API base
GSC_API_BASE = "https://www.googleapis.com/webmasters/v3"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Refresh a little before the real expiry to avoid edge races.
_TOKEN_REFRESH_MARGIN_S = 60


class GSCClient:
    """Google Search Console REST API client with automatic OAuth token refresh.

    All methods are read-only. No write (POST/PUT/DELETE) requests are made.
    """

    def __init__(
        self,
        refresh_token: str,
        access_token: str | None = None,
        token_expires_at: str | None = None,
    ):
        """Initialize the GSC client.

        Args:
            refresh_token: Long-lived Google refresh token (webmasters.readonly scope).
            access_token: Short-lived access token (if already known, avoids initial refresh).
            token_expires_at: ISO timestamp of access token expiry (optional).
        """
        self.refresh_token = refresh_token
        self._access_token: str | None = access_token
        self._expires_at: float = 0.0

        # Parse the ISO timestamp if provided
        if token_expires_at:
            try:
                from datetime import datetime

                exp_dt = datetime.fromisoformat(token_expires_at.replace("Z", "+00:00"))
                self._expires_at = exp_dt.timestamp()
            except (ValueError, TypeError):
                pass

        self.logger = logging.getLogger("GSCClient")

    # --- OAuth token management ---

    async def _ensure_access_token(self) -> str:
        """Return a valid access token, refreshing it if expired/missing.

        Uses GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from environment
        variables for the token refresh exchange.

        Raises:
            Exception: If the token refresh fails (HTTP non-200). The error
                message includes the raw response body for diagnostics
                (e.g. ``invalid_grant`` for expired/revoked refresh tokens).
        """
        if self._access_token and time.time() < (self._expires_at - _TOKEN_REFRESH_MARGIN_S):
            return self._access_token

        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise Exception(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables "
                "are required for GSC token refresh."
            )

        self.logger.debug("Refreshing GSC access token")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"GSC token refresh failed (HTTP {resp.status}): {text}")
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
    ) -> Any:
        """Make an authenticated GSC API request.

        Args:
            method: HTTP method. Only GET is used by this client.
            path: API path under /webmasters/v3 (without the leading slash).
            params: Query parameters (None values dropped).
            json_data: JSON body (for POST requests — not used by read-only tools).

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            Exception: On non-2xx responses with status + body.
        """
        token = await self._ensure_access_token()
        url = f"{GSC_API_BASE}/{path.lstrip('/')}"

        if params:
            params = {k: v for k, v in params.items() if v is not None}

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
                        raise Exception(f"GSC API error (status {response.status}): {text}")
                    return {"success": True, "message": text}

                if response.status >= 400:
                    msg = body.get("error", {}).get("message") if isinstance(body, dict) else None
                    raise Exception(f"GSC API error (status {response.status}): {msg or body}")
                return body

    # --- Sites (properties) ---

    async def list_sites(self) -> dict:
        """List all Search Console properties the user has access to.

        Returns:
            Dict with ``siteEntry`` list, each containing ``siteUrl``,
            ``permissionLevel``, and ``siteUrl``.
        """
        return await self._request("GET", "sites")

    # --- Sitemaps ---

    async def list_sitemaps(
        self,
        site_url: str,
        page_token: str | None = None,
        rows_per_page: int | None = None,
    ) -> dict:
        """List sitemaps submitted for a property.

        Args:
            site_url: The property URL (e.g. ``sc-domain:example.com`` or
                ``https://example.com/``). Must be URL-encoded.
            page_token: Pagination token from a previous response.
            rows_per_page: Max number of sitemaps to return.

        Returns:
            Dict with ``sitemap`` list, each containing ``path``,
            ``lastSubmitted``, ``isPending``, ``isErrors``, ``errors``,
            ``warnings``, ``type``, and ``contents``.
        """
        encoded_site = quote(site_url, safe="")
        params: dict[str, Any] = {}
        if page_token:
            params["pageToken"] = page_token
        if rows_per_page:
            params["rowsPerPage"] = rows_per_page
        return await self._request("GET", f"sites/{encoded_site}/sitemaps", params=params)

    # --- URL Inspection ---

    async def inspect_url(
        self,
        site_url: str,
        inspection_url: str,
        language: str = "en-US",
    ) -> dict:
        """Inspect a URL's indexing status.

        Uses the URL Inspection API endpoint.

        Args:
            site_url: The property URL (e.g. ``sc-domain:example.com``).
            inspection_url: The full URL to inspect. Must be under the
                property's scope (cross-property URLs are rejected by the
                Google API).
            language: Language code for the response (e.g. ``en-US``).

        Returns:
            Dict with ``inspectionResult`` containing ``indexStatusResult``,
            ``mobileUsabilityResult``, ``richResultsResult``, etc.
        """
        # URL Inspection is a POST endpoint (but it is read-only — it doesn't
        # modify any data). The GSC API requires POST for this endpoint.
        url_inspection_base = "https://searchconsole.googleapis.com/v1"
        token = await self._ensure_access_token()
        url = f"{url_inspection_base}/urlInspection/index:inspect"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "inspectionUrl": inspection_url,
            "siteUrl": site_url,
            "languageCode": language,
        }

        self.logger.debug(f"POST {url} (inspect: {inspection_url} on {site_url})")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                try:
                    body = await response.json()
                except Exception:
                    text = await response.text()
                    raise Exception(f"GSC URL Inspection error (status {response.status}): {text}")

                if response.status >= 400:
                    msg = body.get("error", {}).get("message") if isinstance(body, dict) else None
                    raise Exception(
                        f"GSC URL Inspection error (status {response.status}): {msg or body}"
                    )
                return body

    # --- Search Analytics ---

    async def search_analytics(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: list[str] | None = None,
        dimension_filter_groups: list[dict[str, Any]] | None = None,
        type_filter: str = "web",
        rows_limit: int = 1000,
        start_row: int = 0,
        data_state: str = "final",
    ) -> dict:
        """Query Search Analytics data for a property.

        Args:
            site_url: The property URL.
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            dimensions: Dimensions to break down by (e.g. ``["query", "page"]``).
                Allowed: ``query``, ``page``, ``country``, ``device``, ``date``.
            dimension_filter_groups: Optional dimension filter groups for
                narrowing results.
            type_filter: Search type (``web``, ``image``, ``video``, ``news``).
            rows_limit: Maximum number of rows to return (max 25000).
            start_row: Zero-based start row for pagination.
            data_state: ``final`` for finalized data, ``all`` for fresh + final.

        Returns:
            Dict with ``rows`` list, each containing ``keys``, ``clicks``,
            ``impressions``, ``ctr``, and ``position``.
        """
        encoded_site = quote(site_url, safe="")
        # Search Analytics is a POST endpoint (but read-only — it queries data)
        token = await self._ensure_access_token()
        url = f"{GSC_API_BASE}/sites/{encoded_site}/searchAnalytics/query"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "type": type_filter,
            "rowLimit": min(rows_limit, 25000),
            "startRow": start_row,
            "dataState": data_state,
        }
        if dimensions:
            payload["dimensions"] = dimensions
        if dimension_filter_groups:
            payload["dimensionFilterGroups"] = dimension_filter_groups

        self.logger.debug(f"POST {url} (analytics: {start_date} to {end_date})")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                try:
                    body = await response.json()
                except Exception:
                    text = await response.text()
                    raise Exception(
                        f"GSC Search Analytics error (status {response.status}): {text}"
                    )

                if response.status >= 400:
                    msg = body.get("error", {}).get("message") if isinstance(body, dict) else None
                    raise Exception(
                        f"GSC Search Analytics error (status {response.status}): {msg or body}"
                    )
                return body
