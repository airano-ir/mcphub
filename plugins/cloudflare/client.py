"""Cloudflare REST API v4 client — Bearer token auth, fixed API base.

All requests go to ``https://api.cloudflare.com/client/v4``. The token is
a Cloudflare API Token stored per-site (encrypted at rest). Account-scoped
endpoints (Workers, KV, R2) need an account id: the site can configure it
explicitly, otherwise the client discovers the first account the token can
see via ``GET /accounts`` and caches it for the lifetime of the instance.

Error handling keeps Cloudflare's ``errors[].message`` so the user sees the
real reason (e.g. insufficient permissions for a scoped token).
"""

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# Fixed Cloudflare API base — there is no per-user instance URL.
CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareClient:
    """Cloudflare REST API v4 client.

    All methods are async. Write methods intentionally exist — the plugin
    is not read-only — but every tool carries a ``required_scope``
    (read / write / admin) so the hub's universal scope tiers gate them.
    """

    def __init__(self, api_token: str, account_id: str | None = None):
        """Initialize the Cloudflare client.

        Args:
            api_token: Cloudflare API Token (Bearer auth).
            account_id: Optional account id for account-scoped endpoints.
                When omitted, the client discovers the first account the
                token can see on first use.
        """
        self.api_token = api_token
        self.account_id = account_id or ""
        self.api_base = CLOUDFLARE_API_BASE
        self._resolved_account_id: str | None = None
        self.logger = logging.getLogger("CloudflareClient")

    def _get_headers(self, json_body: bool = False) -> dict[str, str]:
        """Build request headers with Bearer auth.

        Args:
            json_body: When True, add ``Content-Type: application/json``.

        Returns:
            Header dict.
        """
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | str:
        """Send an authenticated request to the Cloudflare API.

        Args:
            method: HTTP method (GET/POST/PUT/DELETE).
            path: API path starting with ``/`` (e.g. ``/zones``).
            params: Query parameters (None values are dropped).
            json_data: JSON body (None values are dropped).

        Returns:
            Parsed JSON response body on success.

        Raises:
            Exception: On HTTP errors, with Cloudflare's error messages.
        """
        url = f"{self.api_base}{path}"
        headers = self._get_headers(json_body=json_data is not None)

        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        clean_json = {k: v for k, v in (json_data or {}).items() if v is not None}

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                url,
                params=clean_params,
                headers=headers,
                json=clean_json if clean_json else None,
            ) as resp:
                text = await resp.text()
                if resp.status < 200 or resp.status >= 300:
                    raise Exception(self._format_error(method, url, resp.status, text))
                if "application/json" in (
                    resp.headers.get("Content-Type", "") or "application/json"
                ):
                    try:
                        return await resp.json()
                    except Exception:
                        return text
                return text

    @staticmethod
    def _format_error(method: str, url: str, status: int, body: str) -> str:
        """Build a readable error message from a Cloudflare error response.

        Args:
            method: HTTP method used.
            url: Request URL.
            status: HTTP status code.
            body: Raw response body.

        Returns:
            Error message string.
        """
        try:
            import json

            data = json.loads(body)
            errors = data.get("errors", [])
            if errors:
                detail = "; ".join(e.get("message", str(e)) for e in errors)
                return f"Cloudflare API error (HTTP {status}): {detail}"
        except Exception:
            pass
        return f"Cloudflare API error (HTTP {status}): {body[:300]}"

    async def _resolve_account_id(self) -> str:
        """Return the account id, discovering it when not configured.

        The site may pin ``account_id`` explicitly; otherwise the first
        account visible to the token is used (``GET /accounts``) and cached.

        Returns:
            Account id string.

        Raises:
            Exception: If no account id is configured and the token cannot
                list any account (missing ``account:read`` permission).
        """
        if self.account_id:
            return self.account_id
        if self._resolved_account_id:
            return self._resolved_account_id

        data = await self._request("GET", "/accounts", params={"per_page": 1})
        result = data.get("result", []) if isinstance(data, dict) else []
        if not result:
            raise Exception(
                "No account found: set the site's Account ID, or give the token "
                "the Account:Read permission so it can be discovered automatically."
            )
        self._resolved_account_id = str(result[0].get("id", ""))
        return self._resolved_account_id

    # ── User / token ───────────────────────────────────────────────

    async def verify_token(self) -> dict[str, Any]:
        """Verify the API token and return its status.

        Returns:
            Dict with ``id`` and ``status`` from ``/user/tokens/verify``.
        """
        data = await self._request("GET", "/user/tokens/verify")
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def get_user(self) -> dict[str, Any]:
        """Fetch the authenticated user profile.

        Returns:
            User dict (id, email, username, ...).
        """
        data = await self._request("GET", "/user")
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def list_accounts(self) -> list[dict[str, Any]]:
        """List accounts visible to the token.

        Returns:
            List of account dicts (id, name, ...).
        """
        data = await self._request("GET", "/accounts", params={"per_page": 50})
        return data.get("result", []) if isinstance(data, dict) else []

    # ── Zones ──────────────────────────────────────────────────────

    async def list_zones(
        self,
        name: str | None = None,
        status: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
    ) -> list[dict[str, Any]]:
        """List zones the token can access.

        Args:
            name: Exact zone name filter.
            status: Zone status filter (active, pending, development, ...).
            page: Page number.
            per_page: Results per page (max 50).

        Returns:
            List of zone dicts.
        """
        data = await self._request(
            "GET",
            "/zones",
            params={"name": name, "status": status, "page": page, "per_page": per_page},
        )
        return data.get("result", []) if isinstance(data, dict) else []

    async def get_zone(self, zone_id: str) -> dict[str, Any]:
        """Fetch a single zone by id.

        Args:
            zone_id: Cloudflare zone id.

        Returns:
            Zone dict.
        """
        data = await self._request("GET", f"/zones/{zone_id}")
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def purge_cache(
        self,
        zone_id: str,
        purge_everything: bool | None = None,
        files: list[str] | None = None,
        tags: list[str] | None = None,
        prefixes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Purge cached content for a zone (cache purge permission required).

        Args:
            zone_id: Cloudflare zone id.
            purge_everything: Purge all cached content for the zone.
            files: Specific file URLs to purge.
            tags: Cache-tag based purge.
            prefixes: URL-prefix based purge.

        Returns:
            Cloudflare result dict.
        """
        body: dict[str, Any] = {}
        if purge_everything:
            body["purge_everything"] = True
        if files:
            body["files"] = files
        if tags:
            body["tags"] = tags
        if prefixes:
            body["prefixes"] = prefixes
        if not body:
            raise ValueError(
                "purge_cache requires at least one strategy: purge_everything, files, tags, or prefixes"
            )
        data = await self._request("POST", f"/zones/{zone_id}/purge_cache", json_data=body)
        return data.get("result", {}) if isinstance(data, dict) else {}

    # ── DNS records ────────────────────────────────────────────────

    async def list_dns_records(
        self,
        zone_id: str,
        type: str | None = None,
        name: str | None = None,
        content: str | None = None,
        page: int | None = None,
        per_page: int | None = None,
    ) -> list[dict[str, Any]]:
        """List DNS records for a zone.

        Args:
            zone_id: Cloudflare zone id.
            type: Record type filter (A, AAAA, CNAME, TXT, MX, ...).
            name: Record name filter (substring match).
            content: Record content filter (substring match).
            page: Page number.
            per_page: Results per page (max 100).

        Returns:
            List of DNS record dicts.
        """
        data = await self._request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            params={
                "type": type,
                "name": name,
                "content": content,
                "page": page,
                "per_page": per_page,
            },
        )
        return data.get("result", []) if isinstance(data, dict) else []

    async def get_dns_record(self, zone_id: str, record_id: str) -> dict[str, Any]:
        """Fetch a single DNS record.

        Args:
            zone_id: Cloudflare zone id.
            record_id: DNS record id.

        Returns:
            DNS record dict.
        """
        data = await self._request("GET", f"/zones/{zone_id}/dns_records/{record_id}")
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def create_dns_record(
        self,
        zone_id: str,
        type: str,
        name: str,
        content: str,
        ttl: int | None = None,
        proxied: bool | None = None,
        priority: int | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Create a DNS record (DNS:Edit permission required).

        Args:
            zone_id: Cloudflare zone id.
            type: Record type (A, AAAA, CNAME, TXT, MX, SRV, ...).
            name: DNS record name (e.g. ``www.example.com``).
            content: Record content (IP, target, text, ...).
            ttl: Time to live in seconds (1 = automatic).
            proxied: Whether the record is proxied through Cloudflare.
            priority: Record priority (MX/SRV).
            comment: Free-form comment (max 255 chars).

        Returns:
            Created record dict.
        """
        data = await self._request(
            "POST",
            f"/zones/{zone_id}/dns_records",
            json_data={
                "type": type,
                "name": name,
                "content": content,
                "ttl": ttl,
                "proxied": proxied,
                "priority": priority,
                "comment": comment,
            },
        )
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def update_dns_record(
        self,
        zone_id: str,
        record_id: str,
        type: str | None = None,
        name: str | None = None,
        content: str | None = None,
        ttl: int | None = None,
        proxied: bool | None = None,
        priority: int | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing DNS record (DNS:Edit permission required).

        Only the provided fields are changed; omitted fields keep their
        current value.

        Args:
            zone_id: Cloudflare zone id.
            record_id: DNS record id.
            type: Record type (A, AAAA, CNAME, TXT, MX, SRV, ...).
            name: DNS record name.
            content: Record content.
            ttl: Time to live in seconds (1 = automatic).
            proxied: Whether the record is proxied through Cloudflare.
            priority: Record priority (MX/SRV).
            comment: Free-form comment (max 255 chars).

        Returns:
            Updated record dict.
        """
        data = await self._request(
            "PUT",
            f"/zones/{zone_id}/dns_records/{record_id}",
            json_data={
                "type": type,
                "name": name,
                "content": content,
                "ttl": ttl,
                "proxied": proxied,
                "priority": priority,
                "comment": comment,
            },
        )
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def delete_dns_record(self, zone_id: str, record_id: str) -> dict[str, Any]:
        """Delete a DNS record (DNS:Edit permission required; destructive).

        Args:
            zone_id: Cloudflare zone id.
            record_id: DNS record id.

        Returns:
            Cloudflare result dict.
        """
        data = await self._request("DELETE", f"/zones/{zone_id}/dns_records/{record_id}")
        return data.get("result", {}) if isinstance(data, dict) else {}

    # ── Workers ────────────────────────────────────────────────────

    async def list_workers_scripts(self, account_id: str | None = None) -> list[dict[str, Any]]:
        """List Workers scripts for an account (Workers Scripts:Read).

        Args:
            account_id: Account id override; defaults to the site account.

        Returns:
            List of script dicts.
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request("GET", f"/accounts/{acc}/workers/scripts")
        return data.get("result", []) if isinstance(data, dict) else []

    async def get_workers_script(
        self, script_name: str, account_id: str | None = None
    ) -> dict[str, Any]:
        """Fetch Workers script metadata (Workers Scripts:Read).

        Args:
            script_name: Workers script name.
            account_id: Account id override; defaults to the site account.

        Returns:
            Script metadata dict.
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request("GET", f"/accounts/{acc}/workers/scripts/{script_name}")
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def delete_workers_script(
        self, script_name: str, account_id: str | None = None
    ) -> dict[str, Any]:
        """Delete a Workers script (Workers Scripts:Edit; destructive).

        Args:
            script_name: Workers script name.
            account_id: Account id override; defaults to the site account.

        Returns:
            Cloudflare result dict.
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request("DELETE", f"/accounts/{acc}/workers/scripts/{script_name}")
        return data.get("result", {}) if isinstance(data, dict) else {}

    # ── KV ─────────────────────────────────────────────────────────

    async def list_kv_namespaces(
        self, account_id: str | None = None, per_page: int | None = None
    ) -> list[dict[str, Any]]:
        """List KV namespaces for an account (Workers KV Storage:Read).

        Args:
            account_id: Account id override; defaults to the site account.
            per_page: Results per page (max 100).

        Returns:
            List of namespace dicts (id, title).
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request(
            "GET", f"/accounts/{acc}/storage/kv/namespaces", params={"per_page": per_page}
        )
        return data.get("result", []) if isinstance(data, dict) else []

    async def create_kv_namespace(
        self, title: str, account_id: str | None = None
    ) -> dict[str, Any]:
        """Create a KV namespace (Workers KV Storage:Edit).

        Args:
            title: Namespace title (must be unique within the account).
            account_id: Account id override; defaults to the site account.

        Returns:
            Created namespace dict (id, title).
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request(
            "POST", f"/accounts/{acc}/storage/kv/namespaces", json_data={"title": title}
        )
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def delete_kv_namespace(
        self, namespace_id: str, account_id: str | None = None
    ) -> dict[str, Any]:
        """Delete a KV namespace and ALL its keys (Workers KV Storage:Edit; destructive).

        Args:
            namespace_id: KV namespace id.
            account_id: Account id override; defaults to the site account.

        Returns:
            Cloudflare result dict.
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request(
            "DELETE", f"/accounts/{acc}/storage/kv/namespaces/{namespace_id}"
        )
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def list_kv_keys(
        self,
        namespace_id: str,
        cursor: str | None = None,
        limit: int | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """List keys in a KV namespace (Workers KV Storage:Read).

        Args:
            namespace_id: KV namespace id.
            cursor: Pagination cursor from a previous response.
            limit: Max keys per page (default 100).
            account_id: Account id override; defaults to the site account.

        Returns:
            Dict with ``keys`` list, ``cursor`` (if more pages), and
            ``list_complete`` flag.
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request(
            "GET",
            f"/accounts/{acc}/storage/kv/namespaces/{namespace_id}/keys",
            params={"cursor": cursor, "limit": limit},
        )
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def get_kv_value(
        self, namespace_id: str, key_name: str, account_id: str | None = None
    ) -> str:
        """Read a single KV value (Workers KV Storage:Read).

        Args:
            namespace_id: KV namespace id.
            key_name: Key name.
            account_id: Account id override; defaults to the site account.

        Returns:
            The stored value as a string.
        """
        acc = account_id or (await self._resolve_account_id())
        result = await self._request(
            "GET", f"/accounts/{acc}/storage/kv/namespaces/{namespace_id}/values/{key_name}"
        )
        if isinstance(result, dict):
            return str(result)
        return str(result)

    async def put_kv_value(
        self,
        namespace_id: str,
        key_name: str,
        value: str,
        expiration: int | None = None,
        expiration_ttl: int | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """Write a KV value (Workers KV Storage:Edit).

        Args:
            namespace_id: KV namespace id.
            key_name: Key name (max 512 bytes).
            value: Value to store (max 25 MiB).
            expiration: Absolute expiration as Unix timestamp.
            expiration_ttl: Relative expiration in seconds from now.
            account_id: Account id override; defaults to the site account.

        Returns:
            Cloudflare result dict.
        """
        acc = account_id or (await self._resolve_account_id())
        params = {"expiration": expiration, "expiration_ttl": expiration_ttl}
        clean_params = {k: v for k, v in params.items() if v is not None}
        url = (
            f"{self.api_base}/accounts/{acc}/storage/kv/namespaces/{namespace_id}/values/{key_name}"
        )
        if clean_params:
            from urllib.parse import urlencode

            url = f"{url}?{urlencode(clean_params)}"
        headers = self._get_headers()
        headers["Content-Type"] = "text/plain"
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.put(url, headers=headers, data=value.encode()) as resp:
                text = await resp.text()
                if resp.status < 200 or resp.status >= 300:
                    raise Exception(self._format_error("PUT", url, resp.status, text))
                try:
                    return await resp.json()
                except Exception:
                    return {}

    async def delete_kv_value(
        self, namespace_id: str, key_name: str, account_id: str | None = None
    ) -> dict[str, Any]:
        """Delete a single KV key (Workers KV Storage:Edit; destructive).

        Args:
            namespace_id: KV namespace id.
            key_name: Key name.
            account_id: Account id override; defaults to the site account.

        Returns:
            Cloudflare result dict.
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request(
            "DELETE", f"/accounts/{acc}/storage/kv/namespaces/{namespace_id}/values/{key_name}"
        )
        return data.get("result", {}) if isinstance(data, dict) else {}

    # ── R2 ─────────────────────────────────────────────────────────

    async def list_r2_buckets(
        self, cursor: str | None = None, per_page: int | None = None, account_id: str | None = None
    ) -> dict[str, Any]:
        """List R2 buckets for an account (R2:Read permission).

        Args:
            cursor: Pagination cursor from a previous response.
            per_page: Max buckets per page (default 20).
            account_id: Account id override; defaults to the site account.

        Returns:
            Dict with ``buckets`` list and ``cursor``.
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request(
            "GET", f"/accounts/{acc}/r2/buckets", params={"cursor": cursor, "per_page": per_page}
        )
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def get_r2_bucket(
        self, bucket_name: str, account_id: str | None = None
    ) -> dict[str, Any]:
        """Fetch R2 bucket metadata (R2:Read permission).

        Args:
            bucket_name: Bucket name.
            account_id: Account id override; defaults to the site account.

        Returns:
            Bucket dict.
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request("GET", f"/accounts/{acc}/r2/buckets/{bucket_name}")
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def create_r2_bucket(
        self, bucket_name: str, account_id: str | None = None
    ) -> dict[str, Any]:
        """Create an R2 bucket (R2:Edit permission).

        Bucket names: 3-63 lowercase letters, digits and hyphens, must
        start/end with a letter or digit.

        Args:
            bucket_name: Bucket name.
            account_id: Account id override; defaults to the site account.

        Returns:
            Cloudflare result dict.
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request(
            "POST", f"/accounts/{acc}/r2/buckets", json_data={"name": bucket_name}
        )
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def delete_r2_bucket(
        self, bucket_name: str, account_id: str | None = None
    ) -> dict[str, Any]:
        """Delete an R2 bucket and its objects (R2:Edit; destructive).

        Args:
            bucket_name: Bucket name.
            account_id: Account id override; defaults to the site account.

        Returns:
            Cloudflare result dict.
        """
        acc = account_id or (await self._resolve_account_id())
        data = await self._request("DELETE", f"/accounts/{acc}/r2/buckets/{bucket_name}")
        return data.get("result", {}) if isinstance(data, dict) else {}
