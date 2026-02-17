"""
Supabase REST API Client (Self-Hosted)

Handles all HTTP communication with Supabase Self-Hosted APIs.
All requests go through Kong API Gateway on single base URL.

APIs:
- PostgREST (/rest/v1/) - Database CRUD
- GoTrue (/auth/v1/) - Authentication
- Storage (/storage/v1/) - File storage
- Edge Functions (/functions/v1/) - Serverless
- postgres-meta (/pg/) - Database admin
"""

import base64
import logging
from typing import Any

import aiohttp

class SupabaseClient:
    """
    Supabase Self-Hosted API client.

    All requests go through Kong gateway on single base URL.
    Uses JWT-based authentication with anon_key or service_role_key.
    """

    def __init__(self, base_url: str, anon_key: str, service_role_key: str):
        """
        Initialize Supabase API client.

        Args:
            base_url: Supabase instance URL (Kong gateway)
            anon_key: Public API key (RLS protected)
            service_role_key: Admin API key (bypasses RLS)
        """
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key
        self.service_role_key = service_role_key

        # Initialize logger
        self.logger = logging.getLogger(f"SupabaseClient.{base_url}")

    def _get_headers(
        self, use_service_role: bool = False, additional_headers: dict | None = None
    ) -> dict[str, str]:
        """
        Get request headers with API key authentication.

        Args:
            use_service_role: Use service_role_key (bypasses RLS)
            additional_headers: Additional headers to include

        Returns:
            Dict: Headers with authentication
        """
        key = self.service_role_key if use_service_role else self.anon_key

        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if additional_headers:
            headers.update(additional_headers)

        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        data: bytes | None = None,
        headers_override: dict | None = None,
        use_service_role: bool = False,
    ) -> Any:
        """
        Make authenticated request to Supabase API.

        Args:
            method: HTTP method
            endpoint: API endpoint (with leading /)
            params: Query parameters
            json_data: JSON body data
            data: Raw binary data (for file uploads)
            headers_override: Override/add headers
            use_service_role: Use service_role_key

        Returns:
            API response

        Raises:
            Exception: On API errors
        """
        url = f"{self.base_url}{endpoint}"

        headers = self._get_headers(use_service_role, headers_override)

        # Remove Content-Type for binary data
        if data is not None:
            headers.pop("Content-Type", None)

        # Filter None values
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        if json_data:
            json_data = {k: v for k, v in json_data.items() if v is not None}

        self.logger.debug(f"{method} {url}")

        async with aiohttp.ClientSession() as session:
            kwargs = {
                "method": method,
                "url": url,
                "headers": headers,
            }

            if params:
                kwargs["params"] = params
            if json_data:
                kwargs["json"] = json_data
            if data:
                kwargs["data"] = data

            async with session.request(**kwargs) as response:
                self.logger.debug(f"Response status: {response.status}")

                # Handle 204 No Content
                if response.status == 204:
                    return {"success": True}

                # Handle binary responses (file downloads)
                content_type = response.headers.get("Content-Type", "")
                if "application/json" not in content_type and response.status < 400:
                    # Return binary data as base64
                    binary_data = await response.read()
                    return {
                        "data": base64.b64encode(binary_data).decode(),
                        "content_type": content_type,
                        "size": len(binary_data),
                    }

                # Parse JSON response
                try:
                    response_data = await response.json()
                except Exception:
                    response_text = await response.text()
                    if response.status >= 400:
                        raise Exception(
                            f"Supabase API error (status {response.status}): {response_text}"
                        )
                    return {"success": True, "message": response_text}

                # Check for errors
                if response.status >= 400:
                    error_msg = self._extract_error_message(response_data)
                    raise Exception(f"Supabase API error (status {response.status}): {error_msg}")

                return response_data

    def _extract_error_message(self, response_data: Any) -> str:
        """Extract error message from various response formats."""
        if isinstance(response_data, dict):
            # PostgREST error format
            if "message" in response_data:
                return response_data["message"]
            # GoTrue error format
            if "error_description" in response_data:
                return response_data["error_description"]
            if "msg" in response_data:
                return response_data["msg"]
            if "error" in response_data:
                return response_data["error"]
        return str(response_data)

    # =====================
    # POSTGREST (Database)
    # =====================

    async def query_table(
        self,
        table: str,
        select: str = "*",
        filters: list[dict] | None = None,
        order: str | None = None,
        limit: int = 100,
        offset: int = 0,
        use_service_role: bool = False,
    ) -> list[dict]:
        """
        Query data from a table.

        Args:
            table: Table name
            select: Columns to select
            filters: List of filter conditions
            order: Order by clause (e.g., "created_at.desc")
            limit: Maximum rows
            offset: Offset for pagination
        """
        params = {"select": select, "limit": limit, "offset": offset}

        if order:
            params["order"] = order

        # Build filter query string
        headers = {}
        if filters:
            for f in filters:
                col = f.get("column")
                op = f.get("operator", "eq")
                val = f.get("value")
                if col and val is not None:
                    params[col] = f"{op}.{val}"

        # Request single objects as array
        headers["Accept"] = "application/json"

        return await self.request(
            "GET",
            f"/rest/v1/{table}",
            params=params,
            headers_override=headers,
            use_service_role=use_service_role,
        )

    async def insert_rows(
        self,
        table: str,
        rows: list[dict],
        upsert: bool = False,
        on_conflict: str | None = None,
        use_service_role: bool = False,
    ) -> list[dict]:
        """Insert rows into a table."""
        headers = {"Prefer": "return=representation"}

        if upsert:
            headers["Prefer"] = "return=representation,resolution=merge-duplicates"
            if on_conflict:
                headers["on-conflict"] = on_conflict

        return await self.request(
            "POST",
            f"/rest/v1/{table}",
            json_data=rows if isinstance(rows, list) else [rows],
            headers_override=headers,
            use_service_role=use_service_role,
        )

    async def update_rows(
        self, table: str, data: dict, filters: list[dict], use_service_role: bool = False
    ) -> list[dict]:
        """Update rows matching filters."""
        params = {}
        for f in filters:
            col = f.get("column")
            op = f.get("operator", "eq")
            val = f.get("value")
            if col and val is not None:
                params[col] = f"{op}.{val}"

        headers = {"Prefer": "return=representation"}

        return await self.request(
            "PATCH",
            f"/rest/v1/{table}",
            params=params,
            json_data=data,
            headers_override=headers,
            use_service_role=use_service_role,
        )

    async def delete_rows(
        self, table: str, filters: list[dict], use_service_role: bool = False
    ) -> list[dict]:
        """Delete rows matching filters."""
        params = {}
        for f in filters:
            col = f.get("column")
            op = f.get("operator", "eq")
            val = f.get("value")
            if col and val is not None:
                params[col] = f"{op}.{val}"

        headers = {"Prefer": "return=representation"}

        return await self.request(
            "DELETE",
            f"/rest/v1/{table}",
            params=params,
            headers_override=headers,
            use_service_role=use_service_role,
        )

    async def execute_rpc(
        self, function_name: str, params: dict | None = None, use_service_role: bool = False
    ) -> Any:
        """Execute a stored procedure/function."""
        return await self.request(
            "POST",
            f"/rest/v1/rpc/{function_name}",
            json_data=params or {},
            use_service_role=use_service_role,
        )

    async def count_rows(
        self, table: str, filters: list[dict] | None = None, use_service_role: bool = False
    ) -> int:
        """Count rows in a table."""
        params = {"select": "count"}

        if filters:
            for f in filters:
                col = f.get("column")
                op = f.get("operator", "eq")
                val = f.get("value")
                if col and val is not None:
                    params[col] = f"{op}.{val}"

        headers = {"Accept": "application/json", "Prefer": "count=exact"}

        result = await self.request(
            "HEAD",
            f"/rest/v1/{table}",
            params=params,
            headers_override=headers,
            use_service_role=use_service_role,
        )

        # Count is in Content-Range header for HEAD requests
        # Fallback to query approach
        result = await self.request(
            "GET",
            f"/rest/v1/{table}",
            params={"select": "count", **{k: v for k, v in params.items() if k != "select"}},
            headers_override={"Prefer": "count=exact"},
            use_service_role=use_service_role,
        )

        if isinstance(result, list) and len(result) > 0:
            return result[0].get("count", 0)
        return 0

    # =====================
    # POSTGRES-META (Admin)
    # =====================

    async def list_tables(self, schema: str = "public") -> list[dict]:
        """List all tables in a schema."""
        return await self.request(
            "GET", "/pg/tables", params={"include_system_schemas": "false"}, use_service_role=True
        )

    async def get_table_schema(self, table: str, schema: str = "public") -> dict:
        """Get table schema/columns."""
        columns = await self.request(
            "GET", "/pg/columns", params={"table_name": table}, use_service_role=True
        )
        return {"table": table, "schema": schema, "columns": columns}

    async def list_schemas(self) -> list[dict]:
        """List all database schemas."""
        return await self.request("GET", "/pg/schemas", use_service_role=True)

    async def list_extensions(self) -> list[dict]:
        """List installed extensions."""
        return await self.request("GET", "/pg/extensions", use_service_role=True)

    async def list_policies(self, table: str | None = None) -> list[dict]:
        """List RLS policies."""
        params = {}
        if table:
            params["table_name"] = table
        return await self.request("GET", "/pg/policies", params=params, use_service_role=True)

    async def list_roles(self) -> list[dict]:
        """List database roles."""
        return await self.request("GET", "/pg/roles", use_service_role=True)

    async def list_triggers(self, table: str | None = None) -> list[dict]:
        """List triggers."""
        params = {}
        if table:
            params["table_name"] = table
        return await self.request("GET", "/pg/triggers", params=params, use_service_role=True)

    async def list_functions(self, schema: str = "public") -> list[dict]:
        """List database functions."""
        return await self.request(
            "GET", "/pg/functions", params={"schema": schema}, use_service_role=True
        )

    async def execute_sql(self, query: str) -> Any:
        """Execute raw SQL query."""
        return await self.request(
            "POST", "/pg/query", json_data={"query": query}, use_service_role=True
        )

    # =====================
    # GOTRUE (Auth)
    # =====================

    async def list_users(self, page: int = 1, per_page: int = 50) -> dict[str, Any]:
        """List all users (admin)."""
        return await self.request(
            "GET",
            "/auth/v1/admin/users",
            params={"page": page, "per_page": per_page},
            use_service_role=True,
        )

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Get user by ID."""
        return await self.request("GET", f"/auth/v1/admin/users/{user_id}", use_service_role=True)

    async def create_user(
        self,
        email: str,
        password: str,
        email_confirm: bool = False,
        phone: str | None = None,
        user_metadata: dict | None = None,
        app_metadata: dict | None = None,
    ) -> dict[str, Any]:
        """Create a new user."""
        data = {"email": email, "password": password, "email_confirm": email_confirm}
        if phone:
            data["phone"] = phone
        if user_metadata:
            data["user_metadata"] = user_metadata
        if app_metadata:
            data["app_metadata"] = app_metadata

        return await self.request(
            "POST", "/auth/v1/admin/users", json_data=data, use_service_role=True
        )

    async def update_user(
        self,
        user_id: str,
        email: str | None = None,
        password: str | None = None,
        phone: str | None = None,
        email_confirm: bool | None = None,
        phone_confirm: bool | None = None,
        user_metadata: dict | None = None,
        app_metadata: dict | None = None,
        ban_duration: str | None = None,
    ) -> dict[str, Any]:
        """Update user."""
        data = {}
        if email:
            data["email"] = email
        if password:
            data["password"] = password
        if phone:
            data["phone"] = phone
        if email_confirm is not None:
            data["email_confirm"] = email_confirm
        if phone_confirm is not None:
            data["phone_confirm"] = phone_confirm
        if user_metadata:
            data["user_metadata"] = user_metadata
        if app_metadata:
            data["app_metadata"] = app_metadata
        if ban_duration:
            data["ban_duration"] = ban_duration

        return await self.request(
            "PUT", f"/auth/v1/admin/users/{user_id}", json_data=data, use_service_role=True
        )

    async def delete_user(self, user_id: str) -> dict[str, Any]:
        """Delete a user."""
        return await self.request(
            "DELETE", f"/auth/v1/admin/users/{user_id}", use_service_role=True
        )

    async def generate_link(
        self, email: str, link_type: str = "magiclink", redirect_to: str | None = None
    ) -> dict[str, Any]:
        """Generate magic link or recovery link."""
        data = {"email": email, "type": link_type}
        if redirect_to:
            data["redirect_to"] = redirect_to

        return await self.request(
            "POST", "/auth/v1/admin/generate_link", json_data=data, use_service_role=True
        )

    async def list_user_factors(self, user_id: str) -> list[dict]:
        """List user MFA factors."""
        return await self.request(
            "GET", f"/auth/v1/admin/users/{user_id}/factors", use_service_role=True
        )

    async def delete_user_factor(self, user_id: str, factor_id: str) -> dict:
        """Delete a user's MFA factor."""
        return await self.request(
            "DELETE", f"/auth/v1/admin/users/{user_id}/factors/{factor_id}", use_service_role=True
        )

    # =====================
    # STORAGE
    # =====================

    async def list_buckets(self) -> list[dict]:
        """List all storage buckets."""
        return await self.request("GET", "/storage/v1/bucket", use_service_role=True)

    async def get_bucket(self, bucket_id: str) -> dict:
        """Get bucket details."""
        return await self.request("GET", f"/storage/v1/bucket/{bucket_id}", use_service_role=True)

    async def create_bucket(
        self,
        name: str,
        public: bool = False,
        file_size_limit: int | None = None,
        allowed_mime_types: list[str] | None = None,
    ) -> dict:
        """Create a new bucket."""
        data = {"name": name, "public": public}
        if file_size_limit:
            data["file_size_limit"] = file_size_limit
        if allowed_mime_types:
            data["allowed_mime_types"] = allowed_mime_types

        return await self.request(
            "POST", "/storage/v1/bucket", json_data=data, use_service_role=True
        )

    async def update_bucket(
        self,
        bucket_id: str,
        public: bool | None = None,
        file_size_limit: int | None = None,
        allowed_mime_types: list[str] | None = None,
    ) -> dict:
        """Update bucket settings."""
        data = {}
        if public is not None:
            data["public"] = public
        if file_size_limit:
            data["file_size_limit"] = file_size_limit
        if allowed_mime_types:
            data["allowed_mime_types"] = allowed_mime_types

        return await self.request(
            "PUT", f"/storage/v1/bucket/{bucket_id}", json_data=data, use_service_role=True
        )

    async def delete_bucket(self, bucket_id: str) -> dict:
        """Delete a bucket."""
        return await self.request(
            "DELETE", f"/storage/v1/bucket/{bucket_id}", use_service_role=True
        )

    async def empty_bucket(self, bucket_id: str) -> dict:
        """Empty a bucket (delete all files)."""
        return await self.request(
            "POST", f"/storage/v1/bucket/{bucket_id}/empty", use_service_role=True
        )

    async def list_files(
        self, bucket: str, path: str = "", limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """List files in a bucket/path."""
        data = {"prefix": path, "limit": limit, "offset": offset}
        return await self.request(
            "POST", f"/storage/v1/object/list/{bucket}", json_data=data, use_service_role=True
        )

    async def upload_file(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        upsert: bool = False,
    ) -> dict:
        """Upload a file."""
        headers = {"Content-Type": content_type}
        if upsert:
            headers["x-upsert"] = "true"

        return await self.request(
            "POST",
            f"/storage/v1/object/{bucket}/{path}",
            data=content,
            headers_override=headers,
            use_service_role=True,
        )

    async def download_file(self, bucket: str, path: str) -> dict:
        """Download a file (returns base64)."""
        return await self.request(
            "GET", f"/storage/v1/object/{bucket}/{path}", use_service_role=True
        )

    async def delete_files(self, bucket: str, paths: list[str]) -> dict:
        """Delete files from bucket."""
        return await self.request(
            "DELETE",
            f"/storage/v1/object/{bucket}",
            json_data={"prefixes": paths},
            use_service_role=True,
        )

    async def move_file(self, bucket: str, from_path: str, to_path: str) -> dict:
        """Move/rename a file."""
        return await self.request(
            "POST",
            "/storage/v1/object/move",
            json_data={"bucketId": bucket, "sourceKey": from_path, "destinationKey": to_path},
            use_service_role=True,
        )

    async def get_public_url(self, bucket: str, path: str) -> str:
        """Get public URL for a file."""
        return f"{self.base_url}/storage/v1/object/public/{bucket}/{path}"

    # =====================
    # EDGE FUNCTIONS
    # =====================

    async def invoke_function(
        self, function_name: str, body: dict | None = None, method: str = "POST"
    ) -> Any:
        """Invoke an Edge Function."""
        return await self.request(
            method,
            f"/functions/v1/{function_name}",
            json_data=body,
            use_service_role=False,  # Use anon key for functions
        )

    # =====================
    # HEALTH CHECK
    # =====================

    async def health_check(self) -> dict[str, Any]:
        """Check Supabase instance health."""
        results = {"healthy": True, "services": {}}

        # Check PostgREST
        try:
            await self.request("GET", "/rest/v1/", use_service_role=True)
            results["services"]["postgrest"] = "ok"
        except Exception as e:
            results["services"]["postgrest"] = f"error: {str(e)}"
            results["healthy"] = False

        # Check GoTrue
        try:
            await self.request("GET", "/auth/v1/health", use_service_role=False)
            results["services"]["gotrue"] = "ok"
        except Exception as e:
            results["services"]["gotrue"] = f"error: {str(e)}"
            results["healthy"] = False

        # Check Storage
        try:
            await self.list_buckets()
            results["services"]["storage"] = "ok"
        except Exception as e:
            results["services"]["storage"] = f"error: {str(e)}"
            results["healthy"] = False

        return results
